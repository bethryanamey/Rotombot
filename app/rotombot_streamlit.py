#!/usr/bin/python3
import warnings
warnings.simplefilter(action='ignore', category=UserWarning)

#TODOs in this document
# This file uses environment variables
# These can be found under environment variables in the azure web app APP-ROTOM-POC-UKS-001

import streamlit as st
from streamlit_chat import message
from streamlit_extras.colored_header import colored_header
from streamlit_extras.add_vertical_space import add_vertical_space
import openai
import os
import pyodbc
from azure.identity import ManagedIdentityCredential
from msal import PublicClientApplication
import struct
import sqlite3
# import sqlite3
import pandas as pd
import subprocess
import re
from profanity_check import predict as profanity_predict
from PIL import Image
import time
import ast
from datetime import datetime

import variables as vr
import hidden_variables as hvr

# BETH'S OPENAI CONNECTION
# key for using OpenAI (this is how they charge you)
# API key is an environment variable that doesn't need to be mentioned
# client = openai.OpenAI(
#   organization=hvr.beths_organisation,
# )

#TODO: msal
#TODO: cache token
# if 'token' not in st.session_state:
#     #TODO: generate token    
#     app = PublicClientApplication(
#         str(os.getenv("APP_CLIENT_ID")),
#         authority=f"https://login.microsoftonline.com/{os.getenv('TENANT_ID')}")
#     result = app.acquire_token_interactive(scopes=["User.Read"])
#     if "access_token" in result:
#         print(result["access_token"])
#     token=None
#     st.session_state['token'] = token

# AZURE OPENAI CONNECTION
client = openai.AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),  
    api_version="2023-10-01-preview",
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    )

deployment_name_4=os.getenv("DEPLOYMENT_NAME_4")
deployment_name_35=os.getenv("DEPLOYMENT_NAME_35")

def select_data_source(data_source):

    if data_source in vr.data_connections:
        return vr.data_connections[data_source]
    else:
        raise ValueError(f"Invalid input. Acceptable values are {', '.join(vr.data_connections.keys())}.")

def connect_to_data(data_store: str = "data_lake_mi", database: str = None):

    if data_store not in ["local_sql_server", "sqlite", "azure_sql_server", "data_lake_mi"]:
        raise Exception(f"Can't connect to data. Data store {data_store} is not recognised. Current options available are 'local_sql_server', 'sqlite', 'azure_sql_server', 'data_lake_mi'.")

    # LOCAL SQL SERVER DATA CONNECTION (Beth's laptop)
    elif data_store == "local_sql_server":
        cnxn = pyodbc.connect(driver='{SQL Server}', server=hvr.local_sql_server, database='Playground',               
                    trusted_connection='yes')

    # SQLITE .db FILE CONNECTION
    elif data_store == "sqlite":
        cnxn = sqlite3.connect(r'/app/data/pokemon.db')

    # AZURE SQL SERVER CONNECTION
    elif data_store == "azure_sql_server":
        sql_server_password = str(os.environ["SQL_SERVER_PASSWORD"])
        cnxn = pyodbc.connect('Driver={ODBC Driver 17 for SQL Server};'
                            'Server=tcp:rotom-db-server.database.windows.net,1433;'
                            'Database='+database+';'
                            'Uid=rotom_container;'
                            'Pwd='+sql_server_password+';'
                            'Server=tcp:rotom-db-server.database.windows.net,1433;'
                            'Database=rotom-db;'
                            'Uid=rotom_container;'
                            'Pwd='+sql_server_password+';'
                            'Encrypt=yes;'
                            'TrustServerCertificate=no;'
                            'Connection Timeout=240;')

    # DATA LAKE CONNECTION (AZURE SYNAPSE)
    # Using a token
    elif data_store in ["data_lake_mi_prod", "data_lake_mi_dev"]:
        objectid = str(os.environ["MI_OBJECT_ID"])
        client_id = str(os.environ["MI_CLIENT_ID"])
        #TODO: use user's token
        credential = ManagedIdentityCredential(
            client_id=client_id
        )
        token = credential.get_token("https://database.windows.net/.default").token.encode("UTF-16-LE")
        token_struct = struct.pack(f'<I{len(token)}s', len(token), token)
        SQL_COPT_SS_ACCESS_TOKEN = 1256

        if data_store == "data_lake_mi_prod":
            server = 'syn-uks-it-osdl-prod-ondemand.sql.azuresynapse.net'
        else:
            server = 'syn-uks-it-osdl-dev-ondemand.sql.azuresynapse.net'

        conStr = 'Driver={ODBC Driver 17 for SQL Server};Server=tcp:'+server+',1433;Database='+database+';'

        cnxn = pyodbc.connect(conStr, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})

    # DATA LAKE CONNECTION (Using user's email to authenticate)
    elif data_store == "data_lake_ia":
        return

    return cnxn

#TODO: use list of schemas to allow user to pick which dataset to use
# Ideally, this should cross check with all dataset option in the dictionary in the variables file
def find_schema_options(cnxn) -> list:
    """
    Display choice of schemas for use to choose (mainly for Azure SQL Server with test datasets)
    """
    schemas_query = """
    select s.name as schema_name, 
        s.schema_id,
        u.name as schema_owner
    from sys.schemas s
    inner join sys.sysusers u
        on u.uid = s.principal_id
    where u.name = 'dbo'
        and s.name != 'dbo'
    order by s.name"""
    schemas = pd.read_sql(schemas_query, cnxn)

    schema_options =  list(schemas.schema_name.unique())

    return schema_options

def create_database_definition_sqlite(cnxn) -> str:

    tables_query = "SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name"
    data_tables = pd.read_sql(tables_query, cnxn)  

    db_str = """"""
    for name in data_tables.name:
        temp_str = f"""Table: {name}\nColumns: """
        foreign_keys_query = f"PRAGMA foreign_key_list({name})"
        foreign_key_info = pd.read_sql(foreign_keys_query, cnxn)
        table_info_query = f"PRAGMA table_info({name})"
        table_info = pd.read_sql(table_info_query, cnxn)
        for col in table_info.itertuples():
            col_name = col.name
            col_type = col.type
            if col.pk == 1:
                col_pk = ", primary key"
            else:
                col_pk = ""

            if col_name in foreign_key_info["from"].unique():
                fk_table = foreign_key_info[foreign_key_info["from"] == col_name]["table"].iloc[0]
                fk_col = foreign_key_info[foreign_key_info["from"] == col_name]["to"].iloc[0]
                col_fk = f", foreign_key references {fk_table}({fk_col})"
            else:
                col_fk = ""

            col_str = f"{col_name} ({col_type}{col_pk}{col_fk})"
            temp_str = temp_str + col_str + ", "
        
        if len(db_str) == 0:
            db_str = temp_str[:-2]
        else:
            db_str = db_str + "\n\n" + temp_str[:-2]

    return db_str

def create_database_definition_sql_server(cnxn, schema) -> str:
    
    tables_query = f"""SELECT 
                        DISTINCT TABLE_NAME AS name
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = '{schema}';"""
    data_tables = pd.read_sql(tables_query, cnxn)  

    db_str = f"""Schema: {schema}\n"""
    db_str = f"""Schema: {schema}\n"""
    for name in data_tables.name:
        temp_str = f"""Table: {name}\nColumns: """
        foreign_keys_query = f"""
        SELECT   
            f.name AS foreign_key_name  
            , COL_NAME(fc.parent_object_id, fc.parent_column_id) AS [from]
            , OBJECT_NAME (f.referenced_object_id) AS [table]  
            , COL_NAME(fc.referenced_object_id, fc.referenced_column_id) AS [to]  
        FROM sys.foreign_keys AS f  
        INNER JOIN sys.foreign_key_columns AS fc   
            ON f.object_id = fc.constraint_object_id 
        WHERE OBJECT_NAME(f.parent_object_id) = '{name}'"""
        foreign_key_info = pd.read_sql(foreign_keys_query, cnxn)
        primary_keys_query = f"""
        SELECT 
            tab.[name] as table_name
            , col.[name] as column_name
        FROM sys.tables tab
        inner join sys.indexes pk
            on tab.object_id = pk.object_id 
            and pk.is_primary_key = 1
        INNER JOIN sys.index_columns ic
            ON ic.object_id = pk.object_id
            AND ic.index_id = pk.index_id
        INNER JOIN sys.columns col
            ON pk.object_id = col.object_id
            AND col.column_id = ic.column_id
        WHERE tab.[name] = '{name}'"""
        primary_key_info = pd.read_sql(primary_keys_query, cnxn)
        table_info_query = f"""
        SELECT 
            TABLE_NAME
            , COLUMN_NAME
            , DATA_TYPE
        FROM information_schema.columns
        WHERE TABLE_NAME = '{name}'"""
        table_info = pd.read_sql(table_info_query, cnxn)
        for col in table_info.itertuples():
            col_name = col.COLUMN_NAME
            col_type = col.DATA_TYPE
            if col_name in primary_key_info["column_name"].unique():
                col_pk = ", primary key"
            else:
                col_pk = ""

            if col_name in foreign_key_info["from"].unique():
                fk_table = foreign_key_info[foreign_key_info["from"] == col_name]["table"].iloc[0]
                fk_col = foreign_key_info[foreign_key_info["from"] == col_name]["to"].iloc[0]
                col_fk = f", foreign_key references {fk_table}({fk_col})"
            else:
                col_fk = ""

            col_str = f"{col_name} ({col_type}{col_pk}{col_fk})"
            temp_str = temp_str + col_str + ", "
        
        if len(db_str) == 0:
            db_str = temp_str[:-2]
        else:
            db_str = db_str + "\n\n" + temp_str[:-2]

    return db_str

def log_conversation(what_do_they_want, graph_df, data_df):
    """
    Record state of conversation -> use this to monitor usage and error handling
    """
    with open("rotom_usage_log.txt", "a") as myfile:
        # TODO: include user session id
        myfile.write("date:"+datetime.now().strftime(format="%d/%m/%Y %H:%M"))
        myfile.write("\n\n")
        if what_do_they_want:
            myfile.write("User requested: "+what_do_they_want)
            myfile.write("\n\n")
        myfile.write(str(graph_df))
        myfile.write("\n\n")
        myfile.write(str(data_df))
        myfile.write("\n\n")


def log_openai_use(model, messages, response):
    """
    Having called API, log input and output
    """
    to_log = {
        "date":datetime.now().strftime(format="%d/%m/%Y %H:%M"),
        "model":model,
        "messages":messages,
        "response":response
    }
    with open("openai_log.txt", "a") as myfile:
        myfile.write(str(to_log))
        myfile.write("\n\n")

    return

# reset conversation
def on_btn_click(graph_df, data_df, what_do_they_want, profanity=False):
    """
    Reset the conversation to start again
    If they were rude, don't let them do anything else
    """
    st.session_state['generated'] = [{'type': 'text', 'data': f"Hi! I'm Rotom, your automatic analysis assistant. I'm currently connected to the {vr.data_connections[vr.chosen_data_source]['friendly_name']} dataset.\nWhat would you like to create? A graph or a data table/summarisation?"}]
    st.session_state['past'] = ['Hi!']
    st.session_state.what_do_they_want = vr.what_do_they_want
    st.session_state.graph_df = vr.graph_df.copy()
    st.session_state.data_df = vr.data_df.copy()
    st.session_state.plots = []

    if profanity:
        # the end of chatbot
        what_do_they_want = "Nothing"
    else:
        # go back to the very beginning
        what_do_they_want = None

    graph_df.loc[:, "completed"] = False
    graph_df.loc[:, "input"] = None
    data_df.loc[:, "input"] = None

    return graph_df, data_df, what_do_they_want

def get_text():
    """
    box for requesting text from the user
    """
    input_text = st.text_input("You: ", "", key="input")

    return input_text

def retrieve_next_prompt_from_df(df, stage_of_next_step):
    """
    Find next step based on previously completed and update df to show new response has been generated
    """
    # send them next prompt
    next_step = df[(df.stage == stage_of_next_step) & (df.completed == False)].iloc[0]
    # update table to show we have requested it
    variable = next_step["variable"]
    df.loc[df.variable == variable, "completed"] = True
    # get response to send to user
    response = next_step["prompt"]

    return response, df

def update_last_completed_step(df, stage_of_completed_step, input_text):
    """
    Add users input to dataframe in the correct position
    """
    last_completed_step = df[(df.stage == stage_of_completed_step) & (df.completed == True)].iloc[-1]
    last_completed_variable = last_completed_step["variable"]
    df.loc[df.variable == last_completed_variable, "input"] = input_text

    return df

def save_previous_content(graph_df, var):
    """
    If user isn't happy, save previous question and answer from chatgpt
    """
    previous_var = "previous_" + var
    graph_df.loc[graph_df.variable == previous_var, "input"] = graph_df[graph_df.variable == var]["input"].iloc[0]

    return graph_df


def handle_graph_generation(input_text: str, graph_df: pd.DataFrame):
    """
    Use updates in the graph_df to understand progression of conversation and help with creating a visual.
    Everytime the user inputs text, the entire python script reruns. Therefore, the conversation is cached and needs to be checked with every message. 
        input_text: str, text inputted by the user
        graph_df: pd.DataFrame, table containing conversation information, prompts, and whether a step has been completed (cached conversation)
    """
    # intialise variable (this will become None if we are finished with making a graph)
    what_do_they_want = 'graph'
    # this will only change if we create an image, code, or break
    return_type = 0

    # we know nothing about what the user wants
    if all(graph_df["completed"] == False):
        response, graph_df = retrieve_next_prompt_from_df(graph_df, stage_of_next_step=1)

    # we know something about what the user wants but not all of it
    elif any(graph_df[graph_df.stage == 1]["completed"] == False):
        # get the last step completed and update with input
        graph_df = update_last_completed_step(graph_df, stage_of_completed_step=1, input_text=input_text)
        response, graph_df = retrieve_next_prompt_from_df(graph_df, stage_of_next_step=1)

    # we know everything about what the user wants but it hasn't been executed/no changes requested
    elif all(graph_df[graph_df.stage == 1]["completed"] == True) and all(graph_df[(graph_df.stage >= 2)]["completed"] == False):
        # if we haven't been here before, get the last step completed and update with input
        if all(graph_df[graph_df.stage == 6]["input"].isnull()):
            graph_df = update_last_completed_step(graph_df, stage_of_completed_step=1, input_text=input_text)

        # generate graph
        data_required = graph_df[graph_df.variable == "data_required"]["input"].iloc[0]
        visualisation_description = graph_df[graph_df.variable == "visualisation_description"]["input"].iloc[0]
        customisation_options = graph_df[graph_df.variable == "customisation_options"]["input"].iloc[0]

        # now using session state instead of variables.py
        # nth_plot = len(vr.plots)
        nth_plot = len(st.session_state['plots'])
        response = 'temp_plot{}.png'.format(nth_plot)
        # vr.plots.append(response)
        st.session_state['plots'].append(response)
        return_type = 1

        previous_SQL_messages = None
        previous_python_messages = None
        previous_SQL_gpt_response = None
        previous_python_gpt_response = None
        data_changes = None
        visual_changes = None

        # check whether we are here because user requested visual changes    
        if any(~graph_df[graph_df.stage == 7]["input"].isnull()):           
            graph_changes_requested = graph_df[graph_df.variable == "visual_changes"]["input"].iloc[0]
            if graph_changes_requested:
                previous_python_messages = ast.literal_eval(graph_df[graph_df.variable == "previous_python_messages"]["input"].iloc[0])
                previous_python_gpt_response = graph_df[graph_df.variable == "previous_python_gpt_response"]["input"].iloc[0]
                visual_changes = graph_df[graph_df.variable == "visual_changes"]["input"].iloc[0]
            data_changes_requested = graph_df[graph_df.variable == "data_changes"]["input"].iloc[0]
            if data_changes_requested:
                previous_SQL_messages = ast.literal_eval(graph_df[graph_df.variable == "previous_SQL_messages"]["input"].iloc[0])
                previous_SQL_gpt_response = graph_df[graph_df.variable == "previous_SQL_gpt_response"]["input"].iloc[0]
                data_changes = graph_df[graph_df.variable == "data_changes"]["input"].iloc[0]

        # either no changes have been requested and this is the first attempt or data changes have been requested
        if (data_changes == None and visual_changes == None) or data_changes != None:
            SQL_query, data, SQL_messages, SQL_gpt_response = automate_summarisation(
                                                                data_required, 
                                                                data_for_graph=True,
                                                                previous_sql_messages=previous_SQL_messages, 
                                                                previous_sql_result=previous_SQL_gpt_response,
                                                                data_changes=data_changes)
            graph_df.loc[graph_df.variable == "SQL_query", "input"] = SQL_query
            graph_df.loc[graph_df.variable == "SQL_messages", "input"] = str(SQL_messages)
            graph_df.loc[graph_df.variable == "SQL_gpt_response", "input"] = SQL_gpt_response
        # visual change has been requested but no data change => use data saved locally
        else:
            data = pd.read_csv("temp_data.csv")
        plotting_code, python_messages, python_gpt_response = automate_visualisation(
                                                            data, 
                                                            visualisation_description, 
                                                            customisation_options, 
                                                            plot_save_name=response, 
                                                            previous_python_messages=previous_python_messages, 
                                                            previous_python_result=previous_python_gpt_response, 
                                                            visual_changes=visual_changes)

        # save results            
        graph_df.loc[graph_df.variable == "plotting_code", "input"] = plotting_code
        graph_df.loc[graph_df.variable == "python_messages", "input"] = str(python_messages)
        graph_df.loc[graph_df.variable == "python_gpt_response", "input"] = python_gpt_response
        graph_df.loc[graph_df.stage == 2, "completed"] = True

    # graph has been created, ask for if they want to know how it was made
    elif all(graph_df[(graph_df.stage == 2)]["completed"] == True) and all(graph_df[(graph_df.stage == 3)]["completed"] == False):
        response, graph_df = retrieve_next_prompt_from_df(graph_df, stage_of_next_step=3)

    # user has said whether they want to know how it was made (not all "completed" are True otherwise previous elif would have been satisified)
    elif all(graph_df[(graph_df.stage == 2)]["completed"] == True) and any(graph_df[(graph_df.stage == 3)]["completed"] == False):
        # have dealt with the request of whether they want to show work or not
        # (if input has been added to the table)
        if not graph_df[graph_df.variable == "show_work"]["input"].isnull().all():
            response, graph_df = retrieve_next_prompt_from_df(graph_df, stage_of_next_step=3)
        # otherwise, need to handle users request to see how the result was made
        # user wants to know
        elif "yes" in input_text.lower():
            SQL_query = graph_df[graph_df.variable == "SQL_query"]["input"].iloc[0]
            plotting_code = graph_df[graph_df.variable == "plotting_code"]["input"].iloc[0]
            response = "{}#[GAP]#{}".format(SQL_query, plotting_code)
            return_type = 2
            graph_df.loc[graph_df.variable == "show_work", "input"] = input_text
        # user doesn't want to know, do nothing 
        else:
            response = ""
            return_type = -1
            graph_df.loc[graph_df.variable == "show_work", "input"] = input_text        

    # we've requested all feedback - we know if they want to see work and we know if they're happy
    elif all(graph_df[(graph_df.stage == 3)]["completed"] == True) and all(graph_df[(graph_df.stage >= 4)]["completed"] == False):                
        # last completed will be them telling us theyre' happy
        graph_df = update_last_completed_step(graph_df, stage_of_completed_step=3, input_text=input_text)
        # user was happy, restart
        if 'yes' in input_text.lower():
            # done with making a graph
            what_do_they_want = None
            response = graph_df[graph_df.stage == 4]["prompt"].iloc[0]
            graph_df.loc[:, "completed"] = False
            graph_df.loc[:, "input"] = None
        # user wasn't happy, begin asking for more feedback
        if "no" in input_text.lower():
            # not going to graph_end variable
            graph_df.loc[graph_df.stage == 4, "completed"] = "Skip"
            response, graph_df = retrieve_next_prompt_from_df(graph_df, stage_of_next_step=5)

    # user ain't happy, ask for feedback (find out if it was the graph design or the data or both)
    elif all(graph_df[(graph_df.stage == 6)]["completed"]) == False:
        graph_df = update_last_completed_step(graph_df, stage_of_completed_step=5, input_text=input_text)
        for var in ["SQL_messages", "python_messages", "SQL_gpt_response", "python_gpt_response"]:
            graph_df = save_previous_content(graph_df, var)
        graph_df.loc[graph_df.stage == 6, "completed"] = True

        if "both" in input_text.lower() or ("data" in input_text.lower() and "graph" in input_text.lower()):                    
            response, graph_df = retrieve_next_prompt_from_df(graph_df, stage_of_next_step=7)
        elif "data" in input_text.lower():
            # don't worry about graph
            graph_df.loc[graph_df.variable == "visual_changes", "completed"] = "Skip"
            response, graph_df = retrieve_next_prompt_from_df(graph_df, stage_of_next_step=7)
        elif "graph" in input_text.lower():                    
            # don't worry about data
            graph_df.loc[graph_df.variable == "data_changes", "completed"] = "Skip"
            response, graph_df = retrieve_next_prompt_from_df(graph_df, stage_of_next_step=7)
        else:
            response = "I didn't understand. Can you rephrase the input ('graph', 'data', or 'both')."

    # haven't collected all the necessary feedback from the user
    elif not all(graph_df[(graph_df.stage == 7)]["completed"]) in ["Skip", True]:  
        graph_df = update_last_completed_step(graph_df, stage_of_completed_step=7, input_text=input_text)
        response, graph_df = retrieve_next_prompt_from_df(graph_df, stage_of_next_step=7)        

    # all feedback has been given 
    elif all(graph_df["completed"]) in ["Skip", True]:
        graph_df = update_last_completed_step(graph_df, stage_of_completed_step=7, input_text=input_text)      
        # reset parts of graph df so that program goes back to building graph
        # don't delete some previous inputs as we will use them again
        graph_df.loc[graph_df.stage >= 2, "completed"] = False  
        graph_df.loc[graph_df.stage.isin([3, 4, 5]), "input"] = None  
        response = ""
        return_type = -1    

    else:
        response = "Something went wrong. Please try again."

    return response, what_do_they_want, graph_df, return_type

def handle_data_conversation(input_text: str, data_df: pd.DataFrame, graph_df: pd.DataFrame):    
    """
    Use updates in the data_df to understand progression of conversation and help with performing analysis.
    Everytime the user inputs text, the entire python script reruns. Therefore, the conversation is cached and needs to be checked with every message. 
        input_text: str, text inputted by the user
        data_df: pd.DataFrame, table containing conversation information, prompts, and whether a step has been completed in the data conversation (cached conversation)
        graph_df: pd.DataFrame, table containing conversation information, prompts, and whether a step has been completed in the graph conversation (cached conversation)
    """
    # intialise variable
    what_do_they_want = "data"
    # this will only change if we create an image, code, or break
    return_type = 0

    # user no longer wants to make a data summarisation
    if match_reply(input_text, vr.matching_phrases) == 'graph':
        # update what they want
        what_do_they_want = "graph"
        # reset conversation caches                
        graph_df.loc[:, "completed"] = False
        graph_df.loc[:, "input"] = None
        data_df.loc[:, "completed"] = False
        data_df.loc[:, "input"] = None
        return_type = -1
        response = ""

    # user has not yet made a request
    elif all(data_df["completed"] == False):
        response = data_df[data_df.variable == "user_request"].iloc[0]["prompt"]
        data_df.loc[data_df.variable == "user_request", "completed"] = True

    # user has made previous request, result has been generated and they want to see how
    elif match_reply(input_text, vr.matching_phrases) == 'code' and all(data_df[data_df.stage == 2]["completed"] == True):
        SQL_query = data_df[data_df.variable == "SQL_query"]["input"].iloc[0]
        # response = "// Here is the SQL Query used to generate the result:\n{}".format(SQL_query)
        response = SQL_query
        return_type = 4

    # user has made previous request, result has been generated and they are not happy with it
    elif match_reply(input_text, vr.matching_phrases) == 'problem' and all(data_df[data_df.stage == 2]["completed"] == True):
        # save previous request
        data_df.loc[data_df.variable == "previous_messages", "input"] = data_df[data_df.variable == "messages"]["input"].iloc[0]
        data_df.loc[data_df.variable == "previous_response", "input"] = data_df[data_df.variable == "SQL_query"]["input"].iloc[0]
        response, data_df = retrieve_next_prompt_from_df(data_df, 4)

    # user wants to use generated table to create a graph
    elif match_reply(input_text, vr.matching_phrases) == 'visualise' and all(data_df[data_df.stage == 2]["completed"] == True):
        # reset conversation caches                
        graph_df.loc[:, "completed"] = False
        graph_df.loc[:, "input"] = None
        # save table summarisation request as data request for graph
        graph_df.loc[graph_df.variable == "data_required", "input"] = data_df[data_df.variable == "user_request"]["input"].iloc[0]
        graph_df.loc[graph_df.variable == "data_required", "completed"] = True
        response, graph_df = retrieve_next_prompt_from_df(graph_df, 1)
        # reset data conversation                
        data_df.loc[:, "completed"] = False
        data_df.loc[:, "input"] = None
        what_do_they_want = 'graph'

    # assume any other input is a new query to send to OpenAI
    else:
        # user has requested a change
        if data_df[data_df.variable == "data_changes"]["completed"].iloc[0] == True:
            data_df.loc[data_df.variable == "data_changes", "input"] = input_text
            initial_request = data_df[data_df.variable == "user_request"]["input"].iloc[0]
            previous_messages = ast.literal_eval(data_df[data_df.variable == "previous_messages"]["input"].iloc[0])
            previous_response = data_df[data_df.variable == "previous_response"]["input"].iloc[0]
            SQL_query, result, messages, return_type = automate_summarisation(initial_request, previous_sql_messages=previous_messages, previous_sql_result=previous_response, data_changes=input_text)
            # add data changes to user_request
            data_df.loc[data_df.variable == "user_request", "input"] = data_df.loc[data_df.variable == "user_request"]["input"].iloc[0] + " " + data_df.loc[data_df.variable == "data_changes"]["input"].iloc[0]
            # reset data changes
            data_df.loc[data_df.variable == "data_changes", "input"] = None
            data_df.loc[data_df.variable == "data_changes", "completed"] = False
        else:
            data_df.loc[data_df.variable == "user_request", "input"] = input_text
            SQL_query, result, messages, return_type = automate_summarisation(input_text)

        # save results
        data_df.loc[data_df.variable == "SQL_query", "input"] = SQL_query
        data_df.loc[data_df.variable == "messages", "input"] = str(messages)
        data_df.loc[data_df.variable == "result", "input"] = result
        data_df.loc[data_df.stage == 2, "completed"] = True
        # output result
        response = result

    return response, what_do_they_want, data_df, graph_df, return_type

def generate_custom_response_based_on_convo(input_text: str, what_do_they_want: str, graph_df: pd.DataFrame, data_df: pd.DataFrame):
    """
    Based on progress in conversation (what_do_they_want), decide what is needed and execute function for generating necessary responses
        input_text: str, text inputted by the user
        what_do_they_want: str, text detailing what the user has requested, cached to enable conversations to continue with every script run
        graph_df: pd.DataFrame, table containing conversation information, prompts, and whether a step has been completed in the graph conversation (cached conversation)
        data_df: pd.DataFrame, table containing conversation information, prompts, and whether a step has been completed in the data conversation (cached conversation)
    """

    # this will only change if we create an image, code, or break
    return_type = 0

    # we need to figure out what we're helping them with
    if what_do_they_want is None:
        what_do_they_want = match_reply(input_text, vr.matching_phrases)

    # if we didn't manage to match what they wanted to a functionality, ask them again
    if what_do_they_want is None:
        response = "I did not understand you. Can you please rephrase your input?"
    
    elif what_do_they_want == 'rotom':
        what_do_they_want = None
        response = "Rotom is a small, orange Pokémon that has a body of plasma. Its electric-like body can enter some kinds of machines and take control in order to make mischief. As a Pokédex, Rotom has access to data about many different Pokémon species. It was the inspiration for this tool as it was originally only able to analyse Pokémon data!\nWould you like to produce a graph or a data table/summarisation?"

    elif what_do_they_want == "graph":
        response, what_do_they_want, graph_df, return_type = handle_graph_generation(input_text, graph_df)

    # want to make a data summarisation
    elif what_do_they_want == "data":
        response, what_do_they_want, data_df, graph_df, return_type = handle_data_conversation(input_text, data_df, graph_df)

    else:
        response = "Something went wrong. Please try again."

    return response, what_do_they_want, graph_df, data_df, return_type

def generate_response(input_text, what_do_they_want, graph_df, data_df):

    # this will only change if we create an image, code, or break
    return_type = 0

    # if they swore before, do nothing
    if what_do_they_want == "Nothing":
        response = ""

    # don't accept swearing
    elif profanity_predict([input_text])[0] == 1:
        response = "Abuse and aggresive language is not tolerated. Goodbye."
        graph_df, data_df, what_do_they_want = on_btn_click(graph_df, data_df, what_do_they_want, profanity=True)

    # let them leave if they want to (don't know why they would but oh well)
    elif make_exit(input_text, vr.exit_commands):
        response = "Ok, have a great day!"
        graph_df, data_df, what_do_they_want = on_btn_click(graph_df, data_df, what_do_they_want, profanity=False)

    # don't end conversation, pursue
    else:
        response, what_do_they_want, graph_df, data_df, return_type = generate_custom_response_based_on_convo(input_text, what_do_they_want, graph_df, data_df)

    return response, what_do_they_want, graph_df, data_df, return_type
      
# check is user wants to end conversation
def make_exit(reply, exit_commands):
    for exit_command in exit_commands:
        # if user has used exit command, end conversation
        if exit_command in reply.lower() or reply.lower == "no":
            return True
      
    return False
  
# identify what the user wants to do
def match_reply(reply, matching_phrases):
    for key, values in matching_phrases.items():
        for regex_pattern in values:
            found_match = re.match(regex_pattern, reply.lower())
            if found_match and key:
                return key
    
    return None

def automate_visualisation(
        data: pd.DataFrame, 
        visualisation_description: str, 
        customisation_options: str = None, 
        plot_save_name: str = "temp_plot", 
        previous_python_messages: list = None,
        previous_python_result: str = None,
        visual_changes: str = None
    ):
    """
    Use plain english texts to automatically create custom visualisation
    ## ASSUMES automate_summarisation FUNCTION HAS BEEN EXECUTED ##
    Can also improve on previous prompts if the rpevious messages and response are inputted
        data: pd.DataFrame, df containing data obtained when SQL query was executed in automate summarisation function
        visualisation_description: str, description of the visual that the user would like to create. This includes type of plot and axis values
        customisation_options: str, optional, additional features that the visual should include e.g. fig size, colours
        plot_save_name: str, name of plot without file type ending
        previous_python_messages: list, if this has been executed before but user wasn't happy, send previous messages with changes
        previous_python_result: str, result previously returned when the previous_python_messages were sent to OpenAI
    """

    # if this is not the first time calling this function, the data string will be in the previous python messages so we don't need to get data again
    # if it is, we need to generate the data we want to visualise and generate the system of messages to send to OpenAI with our visualisation request
    if not previous_python_messages:
        # only send a sample of data to OpenAI as csv - prevent size of query being too long
        data_string = data.head(10).to_csv(index=False)

        # final visual query
        visual_query = "{}. Please include any necessary imports. Don't include any additional text other than the python script. Assume the data is saved in a csv called temp_data.csv. Make sure the code saves the plot as {}, but it does not need to display the plot (i.e. no plt.show()).".format(visualisation_description, plot_save_name) #Use xkcd sktch-style drawing mode
        if customisation_options != "no":
            visual_query += " Please can you also {}".format(customisation_options)

        # check size of request to OpenAI - if it is too big, it will fail
        messages=[
            {"role": "system", "content": "You are a helpful, knowledgable assistant with a talent for witing python code."},
            {"role": "user", "content": "I'd like a python script to help me with generating a graph from data please. My data is in the next message as a csv."},
            {"role": "assistant", "content": "Please provide the data in the next message as a CSV (Comma-Separated Values) format, and let me know what type of graph you would like to create."},
            {"role": "user", "content": data_string},
            {"role": "assistant", "content": "Sure! I can help you generate graphs from your data. Could you please let me know what specific types of graphs or visualizations you would like to create?"},
            {"role": "user", "content": visual_query}
        ]

    # otherwise, function has been called before and we want to make improvements
    else:
        messages = previous_python_messages
        previous_assistant_content = {"role": "assistant", "content":previous_python_result}
        messages.append(previous_assistant_content)
        next_message = {"role": "user", "content":"This isn't quite what I need. Please can you change something in the python code: {}. Within the code please save it as a new png image called {}.".format(visual_changes, plot_save_name)}
        messages.append(next_message)    

    working = False
    i = 0
    while working == False and i < 5:
        model = "gpt-3.5-turbo-16k"
        
        # send request to OpenAI for python code to plot visual
        response = client.chat.completions.create(
            # when using Beth's API, need to mention model type rather than deployed model e.g. "gpt-3.5-turbo-16k" (variable a few lines above)
            model=deployment_name_35,
            messages=messages
        )
        # log usage
        log_openai_use(model, messages, response.choices[0].message)

        # extract plotting code from openAI
        gpt_response = response.choices[0].message.content
        if "```python" in gpt_response:
            plotting_code = gpt_response.split("```python")[1].split("```")[0]
        else:
            plotting_code = gpt_response.split("```")[1].split("```")[0]

        # save code locally so that it can be executed 
        with open("plotter.py", "w", encoding="utf-8") as f:
            f.write(plotting_code)
            f.close()
                
        try:
            # run code to create visual
            subprocess.run(["python", "plotter.py"])
            subprocess.check_output(['python', "plotter.py"])
            working = True
        except Exception as e:
            i += 1
            # if we have failed 3 times:
            if i == 2:
                raise Exception(e)
            print("Code didn't work: {}".format(e))
            gpt_response_message = {"role": "assistant", "content":gpt_response}
            messages.append(gpt_response_message)
            new_message = {"role": "user", "content":f"This code didn't work. I got this error message: {e}. Please can you try again."}
            messages.append(new_message)
            time.sleep(3)

    # delete code
    os.remove("plotter.py")

    return plotting_code, messages, gpt_response

def automate_summarisation(summarisation_description: str, data_for_graph: bool = False,
        previous_sql_messages: list = None,
        previous_sql_result: str = None,
        data_changes: str = None):
    """
    Use plain english texts to automatically create data summarisations
        summarisation_description: str, description of the summarisation the uesr would like to create
    """
    # TO CHANGE DATA SOURCE, change vr.chosen_data_source
    data_source_info = select_data_source(vr.chosen_data_source)
    cnxn = connect_to_data(data_store=data_source_info['data_store'], database=data_source_info["database"])
    # description of the available tables 
    db_description = create_database_definition_sql_server(cnxn, data_source_info["schema"])
    # add custom context to database description
    db_description = db_description + data_source_info["db_context"]

    # if this is not the first time calling this function, there will be previous_sql_messages to improve upon 
    if not previous_sql_messages:     
        messages = [
                    {"role": "system", "content": "You are a helpful, knowledgeable assistant with a talent for writing SQL code suitable for an Azure SQL database."},
                    {"role": "user", "content": f"I have a question regarding the data in my database that I'd like to convert into a SQL query. Here is a description of the tables within my SQL database:{db_description} I need a Transact-SQL query to find out {data_source_info['demo_question']}. Only include the SQL query in your response and don't forget to reference the schema."},
                    {"role": "assistant", "content": data_source_info["demo_answer"]},
                    {"role": "user", "content": "That was exactly what I needed, thank you! Can you help me write the SQL query for another question?"},
                    {"role": "assistant", "content": "Of course! I'd be happy to help you with another SQL query. Please go ahead and let me know what you're trying to achieve or what specific question you have in mind"},
                    {"role": "user", "content": f"Here is my next question: '{summarisation_description}'"}
                ]
        
    # otherwise, function has been called before and we want to make improvements
    else:
        messages = previous_sql_messages
        previous_assistant_content = {"role": "assistant", "content":previous_sql_result}
        messages.append(previous_assistant_content)
        next_message = {"role": "user", "content":"This isn't quite what I need. Please can you change something in the SQL query: {}. Make sure not to include any other text in your response apart from the SQL query itself. Thank you!".format(data_changes)}
        messages.append(next_message)   
    
    working = False
    i = 0
    while not working:

        model = "gpt-4"        
        # send request to OpenAI for SQL code
        response = client.chat.completions.create(
            # when using Beth's API, need to mention model type rather than deployed model e.g. "gpt-4" (variable a few lines above)
            model=deployment_name_4,
            messages=messages
        )
        # log usage
        log_openai_use(model, messages, response.choices[0].message)

        gpt_response = response.choices[0].message.content
        print(gpt_response)
        if "```sql" in gpt_response:
            SQL_query = gpt_response.split("```sql")[1].split("```")[0]
        elif "```SQL" in gpt_response:
            SQL_query = gpt_response.split("```SQL")[1].split("```")[0]
        elif "```SQLite" in gpt_response:
            SQL_query = gpt_response.split("```SQLite")[1].split("```")[0]
        elif "```sqlite" in gpt_response:
            SQL_query = gpt_response.split("```sqlite")[1].split("```")[0]
        elif "```" in gpt_response:
            SQL_query = gpt_response.split("```")[1].split("```")[0]
        else:
            SQL_query = gpt_response

        # run query on sql database
        try:
            sql_query_result = pd.read_sql(SQL_query, cnxn)
            working = True
        # query didn't run
        except Exception as e:
            i += 1
            # if we have failed 3 times:
            if i == 2:
                raise Exception(e)
            print("Code didn't work: {}".format(e))
            # ask gpt to fix it
            gpt_response_message = {"role": "assistant", "content":gpt_response}
            messages.append(gpt_response_message)
            new_message = {"role": "user", "content":f"This code didn't work. I got this error message: {e}. Please can you try again."}
            messages.append(new_message)
            time.sleep(3)

    return_type = 3
    if data_for_graph:
        # save data locally
        sql_query_result.to_csv("temp_data.csv", index=False)
        return SQL_query, sql_query_result, messages, gpt_response

    # Reduce the size of a large result
    if len(sql_query_result) > 20:
        sql_query_result = sql_query_result[:20].copy()
    #TODO: if no rows are returned, assume something went wrong
    # if result only has one row, assume they have asked for an aggregation/looking for a particular object
    # ask ChatGPT if they can phrase the answer in a sentence
    elif len(sql_query_result) == 1: # and len(sql_query_result.columns) == 1:
        result_csv = sql_query_result.to_csv(index=False)

        user_question = summarisation_description
        if data_changes:
            gpt_input = f"The customer originally asked '{user_question}' but they requested to make the following change to their query: '{data_changes}'. The answer I got is {result_csv} (in CSV format)"
        else:
            gpt_input = f"The customer asked '{user_question}' and the answer I got is {result_csv} (in CSV format)"

        # write result into a sentence
        sentence_messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "I need help writing a sentence. A customer asked me a data question and this is the data I found. Please could you work this into a sentence so that I can respond to them? Only respond with what I should send to the client and please match the language that they made their request in."},
                {"role": "assistant", "content": "Certainly! Please provide me with the specific data question and the corresponding result, and I'll be happy to help you craft a response sentence."},
                {"role": "user", "content": "The customer asked 'How tall is Mewtwo' and the answer I got is Height_m\n2 (in CSV format)"},
                {"role": "assistant", "content": "Mewtwo is 2 metres tall."},
                {"role": "user", "content": "This is perfect! Thank you. Can you do it again for another question?"},
                {"role": "assistant", "content": "Of course! I'm here to help. Please provide me with the new data question and the corresponding result, and I'll assist you in constructing a response sentence."},
                {"role": "user", "content": gpt_input}
            ]

        model = "gpt-3.5-turbo"        
        # send request to OpenAI for python code to plot visual
        response = client.chat.completions.create(
            # when using Beth's API, need to mention model type rather than deployed model e.g. "gpt-3.5-turbo" (variable a few lines above)
            model=deployment_name_35,
            messages=sentence_messages
        )
        #log usage
        log_openai_use(model, sentence_messages, response.choices[0].message)

        # extract plotting code from openAI
        answer_in_a_sentence = response.choices[0].message.content

        return_type = 0

        return SQL_query, answer_in_a_sentence, messages, return_type

    # if result was more than one row, just return table produced from query
    return SQL_query, sql_query_result, messages, return_type

# page design

st.set_page_config(page_title="Rotom Chatbot")

with st.sidebar:
    st.header('Rotom Chatbot')
    st.subheader('Your Automatic Analysis Assistant')
    st.image('rotom.png', use_column_width=True)
    st.markdown('''
    # About
    Rotom can assist you with building data summarisations, tables, and visualisations all about Pokemon. 
    Just say the question! Not sure where to start? Try asking 'How many Pokemon are there?'
    ''')
    add_vertical_space(2)
    st.write('Made with ❤️ by Beth')

#TODO: add something to the start of the conversation that allows the user to select the schema in the database

# starting session from beginning => initiate chache
if 'generated' not in st.session_state:
    st.session_state['generated'] = [{'type': 'text', 'data': f"Hi! I'm Rotom, your automatic analysis assistant. I'm currently connected to the {vr.data_connections[vr.chosen_data_source]['friendly_name']} dataset.\nWhat would you like to create? A graph or a data table/summarisation?"}]
# if the user has never messaged before
if 'past' not in st.session_state:
    st.session_state['past'] = ['Hi!']
if 'what_do_they_want' not in st.session_state:
    st.session_state['what_do_they_want'] = vr.what_do_they_want
if 'graph_df' not in st.session_state:
    st.session_state['graph_df'] = vr.graph_df.copy()
if 'data_df' not in st.session_state:
    st.session_state['data_df'] = vr.data_df.copy()
if 'plots' not in st.session_state:
    st.session_state['plots'] = []

input_container = st.container()
# a bar below where users enter input
colored_header(label='', description='', color_name='blue-30')
response_container = st.container()

with input_container:
    help_needed = get_text()

return_types = {
    0:"text",
    1:"img",
    2:"code",
    3:"table",
    4:"data_code",
    -1:"break"
}

with response_container:
    # generate response
    if help_needed:
        # updating cache in variables.py
        # response, vr.what_do_they_want, vr.graph_df, vr.data_df, return_type = generate_response(help_needed, vr.what_do_they_want, vr.graph_df, vr.data_df)
        # updating cache using session_state
        response, st.session_state['what_do_they_want'], st.session_state['graph_df'], st.session_state['data_df'], return_type = generate_response(help_needed, st.session_state['what_do_they_want'], st.session_state['graph_df'], st.session_state['data_df'])
        print("\n\n", st.session_state['what_do_they_want'], "\n")
        print("\n", st.session_state['graph_df'], "\n")
        print("\n", st.session_state['data_df'], "\n\n")
        log_conversation(st.session_state['what_do_they_want'], st.session_state['graph_df'], st.session_state['data_df'])
        st.session_state.past.append(help_needed) 
        return_type_str = return_types[return_type]
        st.session_state.generated.append({'type': return_type_str, 'data': response})
        # anything but text is returned   
        if return_type in [1, 2, -1]:
            # create dummy input to fill gap where we don't need users response
            dummy_input = f'{return_type_str} received.'
            # move onto next step (don't need any input)
            # updating cache in variables.py
            # response, vr.what_do_they_want, vr.graph_df, vr.data_df, return_type = generate_response(dummy_input, vr.what_do_they_want, vr.graph_df, vr.data_df)
            response, st.session_state['what_do_they_want'], st.session_state['graph_df'], st.session_state['data_df'], return_type = generate_response(dummy_input, st.session_state['what_do_they_want'], st.session_state['graph_df'], st.session_state['data_df'])
            st.session_state.past.append(dummy_input)

            # if graph was returned again (this is possible when feedback has been given and we are at the end of the cycle)
            if return_type == 1:
                st.session_state.generated.append({'type': 'img', 'data': response})
                # move onto next step (don't need any input)
                # updating cache in variables.py
                # response, vr.what_do_they_want, vr.graph_df, vr.data_df, return_type = generate_response('img received.', vr.what_do_they_want, vr.graph_df, vr.data_df)
                response, st.session_state['what_do_they_want'], st.session_state['graph_df'], st.session_state['data_df'], return_type = generate_response('img received.', st.session_state['what_do_they_want'], st.session_state['graph_df'], st.session_state['data_df'])
                st.session_state.past.append(dummy_input)

            st.session_state.generated.append({'type': 'text', 'data': response})

        # print previous chat
    if st.session_state['generated']:
        for i in range(len(st.session_state['generated'])):
            # print any input from the user that is not a dummy input that we made up to fill in a blank where we don't need the users response
            if st.session_state['past'][i][-10:] != " received.":
                message(st.session_state['past'][i], is_user=True, key=str(i) + '_user', avatar_style="thumbs", seed=2225)
            if st.session_state["generated"][i]['type'] == 'text':
                message(st.session_state["generated"][i]['data'], key=str(i), avatar_style="thumbs", seed=18)
            # code for data table and graph
            elif st.session_state["generated"][i]['type'] == "code":
                sql, python = st.session_state["generated"][i]['data'].split('#[GAP]#')
                message('Here is the SQL query used to extract the data and the Python code used to generate the graph:', key=str(i), avatar_style="thumbs", seed=18)
                st.code(sql.strip(), language='sql')
                st.code(python.strip(), language='python')
            # code generated to create data table/summarisation
            elif st.session_state["generated"][i]['type'] == "data_code":
                message('Here is the SQL query used to generate the result:', key=str(i), avatar_style="thumbs", seed=18)
                st.code(st.session_state["generated"][i]['data'], language='sql')
            elif st.session_state["generated"][i]['type'] == "img":
                image = Image.open(st.session_state["generated"][i]['data'])
                st.image(image)
            elif st.session_state["generated"][i]['type'] == "table":
                data = st.session_state["generated"][i]['data']
                st.table(data)
    
    st.button("Clear Chat", on_click=on_btn_click, args=(st.session_state['graph_df'], st.session_state['data_df'], st.session_state['what_do_they_want'])) 