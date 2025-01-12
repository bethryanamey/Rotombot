#TODOs in this document
#TODO: create way to easily export results: user queries, result, and generated code

import warnings
warnings.simplefilter(action='ignore', category=UserWarning)

import streamlit as st
from streamlit_chat import message
from streamlit_extras.colored_header import colored_header
from streamlit_extras.add_vertical_space import add_vertical_space
import openai
import os
import sqlite3
import pandas as pd
import tiktoken
import subprocess
import re
from profanity_check import predict as profanity_predict
from PIL import Image
import time
import ast

import variables as vr
import hidden_variables as hvr

# key for using OpenAI (this is how they charge you)
openai.api_key_path = hvr.api_key_path

# sqlite connection
cnxn = sqlite3.connect(r'C:\Users\Beth\Documents\Python Scripts\Be Digital\Business MI Dashboards\Rotombot\Rotombot\anonymous.sqlite3\anonymous.sqlite3')

def create_database_definition(cnxn) -> str:

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

# description of the available tables 
data = create_database_definition(cnxn)

# reset conversation
def on_btn_click(graph_df, data_df, what_do_they_want, profanity=False):
    """
    Reset the conversation to start again
    If they were rude, don't let them do anything else
    """
    del st.session_state.past[:]
    del st.session_state.generated[:]
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
        # we need to figure out what we're helping them with
        if what_do_they_want is None:
            what_do_they_want = match_reply(input_text, vr.matching_phrases)
        # if we didn't manage to match what they wanted to a functionality, ask them again
        if what_do_they_want is None:
            response = "I did not understand you. Can you please rephrase your input?"
        
        elif what_do_they_want == 'rotom':
            what_do_they_want = None
            response = "Rotom is a small, orange Pokémon that has a body of plasma. Its electric-like body can enter some kinds of machines and take control in order to make mischief. As a Pokédex, Rotom has access to data about many different Pokémon species.\nWould you like to produce a graph or a data table/summarisation?"

        elif what_do_they_want == "graph":
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
                if all(graph_df[graph_df.variable == "problem"]["input"].isnull()):
                    graph_df = update_last_completed_step(graph_df, stage_of_completed_step=1, input_text=input_text)

                # generate graph
                data_required = graph_df[graph_df.variable == "data_required"]["input"].iloc[0]
                visualisation_description = graph_df[graph_df.variable == "visualisation_description"]["input"].iloc[0]
                customisation_options = graph_df[graph_df.variable == "customisation_options"]["input"].iloc[0]

                nth_plot = len(vr.plots)
                response = 'temp_plot{}.png'.format(nth_plot)
                vr.plots.append(response)
                return_type = 1

                previous_messages = None
                previous_response = None
                visual_changes = None

                # check whether we are here because user requested visual changes    
                if any(~graph_df[graph_df.stage == 6]["input"].isnull()):           
                    graph_changes = graph_df[graph_df.variable == "visual_changes"]["input"].iloc[0]
                    if graph_changes:
                        previous_messages = ast.literal_eval(graph_df[graph_df.variable == "previous_messages"]["input"].iloc[0])
                        previous_response = graph_df[graph_df.variable == "previous_response"]["input"].iloc[0]
                        visual_changes = graph_df[graph_df.variable == "visual_changes"]["input"].iloc[0]

                SQL_query, plotting_code, messages, gpt_response = automate_visualisation(
                                                                    data_required, 
                                                                    visualisation_description, 
                                                                    customisation_options, 
                                                                    plot_save_name=response, 
                                                                    previous_python_messages=previous_messages, 
                                                                    previous_python_result=previous_response, 
                                                                    visual_changes=visual_changes)

                # it didn't work, reset
                if SQL_query == -1:
                    response = "Something went wrong. Please try again.\nPlease describe the data you would like in the visual."
                    graph_df.loc[:, "completed"] = False
                    graph_df.loc[:, "input"] = None

                # save results
                graph_df.loc[graph_df.variable == "SQL_query", "input"] = SQL_query
                graph_df.loc[graph_df.variable == "plotting_code", "input"] = plotting_code
                graph_df.loc[graph_df.variable == "messages", "input"] = str(messages)
                graph_df.loc[graph_df.variable == "gpt_response", "input"] = gpt_response
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
                elif input_text.lower() == "yes":
                    SQL_query = graph_df[graph_df.variable == "SQL_query"]["input"].iloc[0]
                    plotting_code = graph_df[graph_df.variable == "plotting_code"]["input"].iloc[0]
                    response = "SQL Query:\n{}\n\nPython Plotting Code:\n{}".format(SQL_query, plotting_code)
                    return_type = 2
                # user doesn't want to know, do nothing 
                else:
                    response = ""
                    return_type = -1

                # save that we acknowledged this
                graph_df.loc[graph_df.variable == "show_work", "input"] = input_text

            # we've requested all feedback - we know if they want to see work and we know if they're happy
            elif all(graph_df[(graph_df.stage == 3)]["completed"] == True) and all(graph_df[(graph_df.stage >= 4)]["completed"] == False):                
                # last completed will be them telling us theyre' happy
                graph_df = update_last_completed_step(graph_df, stage_of_completed_step=3, input_text=input_text)
                # user was happy, restart
                if input_text.lower() == 'yes':
                    # done with making a graph
                    what_do_they_want = None
                    response = graph_df[graph_df.stage == 4]["prompt"].iloc[0]
                    graph_df.loc[:, "completed"] = False
                    graph_df.loc[:, "input"] = None
                # user wasn't happy, begin asking for more feedback
                if input_text.lower() == "no":
                    # not going to graph_end variable
                    graph_df.loc[graph_df.stage == 4, "completed"] = "Skip"
                    response, graph_df = retrieve_next_prompt_from_df(graph_df, stage_of_next_step=5)

            # user ain't happy, ask for feedback
            # (will have already sent one prompt for stage 5 asking what the problem is)
            elif not all(graph_df[(graph_df.stage >= 5)]["completed"]) in ["Skip", True]:
                graph_df = update_last_completed_step(graph_df, stage_of_completed_step=5, input_text=input_text)
                # only need to update them once
                if graph_df[graph_df.variable == "previous_messages"]["completed"].iloc[0] == False:
                    graph_df.loc[graph_df.variable == "previous_messages", "input"] = graph_df[graph_df.variable == "messages"]["input"].iloc[0]
                    graph_df.loc[graph_df.variable == "previous_response", "input"] = graph_df[graph_df.variable == "gpt_response"]["input"].iloc[0]
                    graph_df.loc[graph_df.variable.isin(["previous_messages", "previous_response"]), "completed"] = True

                things_to_change = graph_df[graph_df.variable == "problem"]["input"].iloc[0]

                if "both" in things_to_change or ("data" in things_to_change and "graph" in things_to_change):                    
                    response, graph_df = retrieve_next_prompt_from_df(graph_df, stage_of_next_step=6)
                elif "data" in things_to_change:
                    # don't worry about graph
                    graph_df.loc[graph_df.variable == "visual_changes", "completed"] = "Skip"
                    response, graph_df = retrieve_next_prompt_from_df(graph_df, stage_of_next_step=6)
                elif "graph" in things_to_change:                    
                    # don't worry about data
                    graph_df.loc[graph_df.variable == "data_changes", "completed"] = "Skip"
                    response, graph_df = retrieve_next_prompt_from_df(graph_df, stage_of_next_step=6)
                else:
                    response = "I didn't understand. Can you rephrase the input ('graph', 'data', or 'both')."

            # all feedback has been given 
            elif all(graph_df["completed"]) in ["Skip", True]:
                graph_df = update_last_completed_step(graph_df, stage_of_completed_step=6, input_text=input_text)

                # if data changes were requested, append them to the previous request
                data_changes_requested = graph_df[graph_df.variable == "data_changes"]["completed"].iloc[0]
                if data_changes_requested == True:
                    data_changes = graph_df[graph_df.variable == "data_changes"]["input"].iloc[0]
                    if data_changes != "":
                        previous_data_request = graph_df[graph_df.variable == "data_required"]["input"].iloc[0]
                        graph_df.loc[graph_df.variable == "data_required", "input"] = previous_data_request + ", " + data_changes            
                
                # if graph changes were requested, these are inputted into automate_visualisation function
                # reset parts of graph df so that program goes back to building graph
                # don't delete some previous inputs as we will use them again
                graph_df.loc[graph_df.stage >= 2, "completed"] = False  
                graph_df.loc[graph_df.stage.isin([2, 3, 4, 5]), "input"] = None  
                response = ""
                return_type = -1    

            else:
                response = "Something went wrong. Please try again."


        # want to make a data summarisation
        elif what_do_they_want == "data":

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
            elif match_reply(input_text, vr.matching_phrases) == 'code' and all(data_df["completed"] == True):
                SQL_query = data_df[data_df.variable == "SQL_query"]["input"].iloc[0]
                response = "Here is the SQL Query used to generate the result:\n{}".format(SQL_query)

            # user wants to use generated table to create a graph
            elif match_reply(input_text, vr.matching_phrases) == 'visualise' and all(data_df["completed"] == True):
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
                data_df.loc[data_df.variable == "user_request", "input"] = input_text
                SQL_query, result, messages, return_type = automate_summarisation(input_text)
                # save results
                data_df.loc[data_df.variable == "SQL_query", "input"] = SQL_query
                data_df.loc[data_df.variable == "messages", "input"] = str(messages)
                data_df.loc[data_df.variable == "result", "input"] = result
                data_df.loc[data_df.stage == 2, "completed"] = True
                # output result
                response = result

        else:
            response = "Something went wrong. Please try again."

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

def num_tokens_from_messages(messages, model="gpt-3.5-turbo"):
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    if model == "gpt-3.5-turbo":  # note: future models may deviate from this
        num_tokens = 0
        for message in messages:
            num_tokens += 4  # every message follows <im_start>{role/name}{content}<im_end>
            for key, value in message.items():
                num_tokens += len(encoding.encode(value))
                if key == "name":  # if there's a name, the role is omitted
                    num_tokens += -1  # role is always required and always 1 token
        num_tokens += 2  # every reply is primed with <im_start>assistant
        return num_tokens
    else:
        raise NotImplementedError(f"""num_tokens_from_messages() is not presently implemented for model {model}.
    See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens.""")

def automate_visualisation(
        data_required: str, 
        visualisation_description: str, 
        customisation_options: str = None, 
        plot_save_name: str = "temp_plot", 
        previous_python_messages: list = None,
        previous_python_result: str = None,
        visual_changes: str = None
    ):
    """
    Use plain english texts to automatically create custom visualisation
    Can also improve on previous prompts if the rpevious messages and response are inputted
        data_required: str, description of data needed for visual
        visualisation_description: str, description of the visual that the user would like to create. This includes type of plot and axis values
        customisation_options: str, optional, additional features that the visual should include e.g. fig size, colours
        plot_save_name: str, name of plot without file type ending
        previous_python_messages: list, if this has been executed before but user wasn't happy, send previous messages with changes
        previous_python_result: str, result previously returned when the previous_python_messages were sent to OpenAI
    """

    # if this is not the first time calling this function, the data string will be in the previous python messages so we don't need to get data again
    # if it is, we need to generate the data we want to visualise and generate the system of messages to send to OpenAI with our visualisation request
    if not previous_python_messages:
        # create SQL query for retrieving data
        #TODO: alter code so that if user isn't happy with the data, they can request a change
        SQL_query, sql_query_result, sql_messages = automate_summarisation(data_required, data_for_graph=True)

        # save result locally and as string as variable
        sql_query_result.to_csv("temp_data.csv", index=False)
        # only send a sample of data to OpenAI - prevent size of query being too longconda
        data_string = sql_query_result.head(10).to_csv(index=False)

        # final visual query
        visual_query = "{}. Please include any necessary imports. Don't include any additional text other than the python script. Assume the data is saved in a csv called temp_data.csv. Make sure the code saves the plot as {}, but it does not need to display the plot (i.e. no plt.show()).".format(visualisation_description, plot_save_name) #Use xkcd sktch-style drawing mode
        if customisation_options != "no":
            visual_query += " Please can you also {}".format(customisation_options)

        # check size of request to OpenAI - if it is too big, it will fail
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "I'd like a python script to help me with generating a graph from data please. My data is in the next message as a csv."},
            {"role": "assistant", "content": "Please provide the data in the next message as a CSV (Comma-Separated Values) format, and let me know what type of graph you would like to create."},
            {"role": "user", "content": data_string},
            {"role": "assistant", "content": "Sure! I can help you generate graphs from your data. Could you please let me know what specific types of graphs or visualizations you would like to create?"},
            {"role": "user", "content": visual_query}
        ]

    # otherwise, function has been called before and we want to make improvements
    else:
        SQL_query = None
        messages = previous_python_messages
        previous_assistant_content = {"role": "assistant", "content":previous_python_result}
        messages.append(previous_assistant_content)
        next_message = {"role": "user", "content":"This isn't quite what I need. Please can you change something in the python code: {}. Within the code please save it as a new png image called {}.".format(visual_changes, plot_save_name)}
        messages.append(next_message)    

    working = False
    i = 0
    while working == False and i < 5:
        i += 1
        model = "gpt-3.5-turbo-16k"
        n_tokens = num_tokens_from_messages(messages)
        if n_tokens > 16384:
            e = "Data for query is too large for ChatGPT. Trying querying a smaller subset of data."
            raise Exception(e)
        
        # send request to OpenAI for python code to plot visual
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages
        )
        # extract plotting code from openAI
        # todo: query has been altered so that it doesn't include any additional text - check this has worked so this won't be needed
        plotting_code = response["choices"][0]["message"]["content"]
        if "```python" in plotting_code:
            plotting_code = plotting_code.split("```python")[1].split("```")[0]
        else:
            plotting_code = plotting_code.split("```")[1].split("```")[0]

        # save code locally so that it can be executed
        # todo: again, is there somewhere else this should be saved? 
        with open("plotter.py", "w", encoding="utf-8") as f:
            f.write(plotting_code)
            f.close()
                
        try:
            # run code to create visual
            subprocess.run(["python", "plotter.py"])
            subprocess.check_output(['python', "plotter.py"])
            working = True
        except Exception as e:
            print("Code didn't work: {}".format(e))
            gpt_response = {"role": "assistant", "content":response["choices"][0]["message"]["content"]}
            messages.append(gpt_response)
            new_message = {"role": "user", "content":"This code didn't work. Please can you try again."}
            messages.append(new_message)
            time.sleep(3)

    if working == False:
        return -1, None, None, None  

    # todo: currently shows image but this may not be needed (just needs to be sent back to frontend)
    # img = cv2.imread(plot_save_name)
    # cv2.imshow("OpenAI Plot", img)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    # delete code
    os.remove("plotter.py")

    return SQL_query, plotting_code, messages, response["choices"][0]["message"]["content"]

def automate_summarisation(summarisation_description: str, data_for_graph: bool = False):
        """
        Use plain english texts to automatically create data summarisations
            summarisation_description: str, description of the summarisation the uesr would like to create
        """

        # # create SQL query for retrieving data
        # response = openai.Completion.create(
        #     model="text-davinci-003",
        #     prompt="### SQL Server tables, with their properties:\n#\n#{}\n#\n### A Transact-SQL query to find out {}. Don't use the word LIMIT.}}".format(data, summarisation_description),
        #     temperature=0,
        #     max_tokens=150,
        #     top_p=1.0,
        #     frequency_penalty=0.0,
        #     presence_penalty=0.0,
        #     stop=["#", ";"]
        # )

        # # extract query from response
        # SQL_query = str(response["choices"][0]["text"])

        # Alternative model for generating SQL queries        
        messages = [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Here is a description of the tables within my SQLite database:\n#\n#{}\n#\n### I need a Transact-SQL query to find out {}.}}".format(data, summarisation_description)},
                ]
        working = False
        i = 0
        while not working:

            model = "gpt-4"
            n_tokens = num_tokens_from_messages(messages)
            if n_tokens > 16384:
                e = "Data for query is too large for ChatGPT. Trying querying a smaller subset of data."
                raise Exception(e)
            
            # send request to OpenAI for python code to plot visual
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages
            )
            gpt_response = response["choices"][0]["message"]["content"]
            if "```sql" in gpt_response:
                SQL_query = gpt_response.split("```sql")[1].split("```")[0]
            elif "```SQL" in gpt_response:
                SQL_query = gpt_response.split("```SQL")[1].split("```")[0]
            else:
                SQL_query = gpt_response.split("```")[1].split("```")[0]

            # run query on sql server database
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
            return SQL_query, sql_query_result, messages

        # if result only has one row, assume they have asked for an aggregation/looking for a particular object
        # ask ChatGPT if they can phrase the answer in a sentence
        #messages = None
        if len(sql_query_result) == 1: # and len(sql_query_result.columns) == 1:
            result_csv = sql_query_result.to_csv(index=False)

            # write result into a sentence
            messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "I need help writing a sentence. A customer asked me a data question and this is the data I found. Please could you work this into a sentence so that I can respond to them? Only respond with what I should send to the client and please match the language that they made their request in."},
                    {"role": "assistant", "content": "Certainly! Please provide me with the specific data question and the corresponding result, and I'll be happy to help you craft a response sentence."},
                    {"role": "user", "content": "The customer asked 'How tall is Mewtwo' and the answer I got is Height_m\n2 (in CSV format)"},
                    {"role": "assistant", "content": "Mewtwo is 2 metres tall."},
                    {"role": "user", "content": "This is perfect! Thank you. Can you do it again for another question?"},
                    {"role": "assistant", "content": "Of course! I'm here to help. Please provide me with the new data question and the corresponding result, and I'll assist you in constructing a response sentence."},
                    {"role": "user", "content": "The customer asked '{}' and the answer I got is {} (in CSV format)".format(summarisation_description, result_csv)}
                ]

            model = "gpt-3.5-turbo"
            n_tokens = num_tokens_from_messages(messages)
            if n_tokens > 4096:
                e = "Data for query is too large for ChatGPT. Trying querying a smaller subset of data."
                raise Exception(e)
            
            # send request to OpenAI for python code to plot visual
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages
            )
            # extract plotting code from openAI
            answer_in_a_sentence = response["choices"][0]["message"]["content"]

            return_type = 0

            return SQL_query, answer_in_a_sentence, messages, return_type

        # if result was more than one row, just return table produced from query
        return SQL_query, sql_query_result, messages, return_type

## page design

st.set_page_config(page_title="Rotom Chatbot")

with st.sidebar:
    st.header('Rotom Chatbot')
    st.subheader('Your Automatic Analysis Assistant')
    st.image('rotom.png', use_column_width=True)
    st.markdown('''
    ## About
    Rotom can assist you with building data summarisations, tables, and visualisations all about Pokemon. 
    Just say the question! Not sure where to start? Try asking 'How many Pokemon are there?'
    ''')
    add_vertical_space(2)
    st.write('Made with ❤️ by Beth')

if 'generated' not in st.session_state:
    st.session_state['generated'] = [{'type': 'text', 'data': "Hi! I'm Rotom, your automatic analysis assistant.\nWhat would you like to create? A graph or a data table/summarisation?"}]
# if the user has never messaged before
if 'past' not in st.session_state:
    st.session_state['past'] = ['Hi!']

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
    -1:"break"
}

with response_container:
    if help_needed:
        response, vr.what_do_they_want, vr.graph_df, vr.data_df, return_type = generate_response(help_needed, vr.what_do_they_want, vr.graph_df, vr.data_df)
        print("\n\n", vr.data_df, "\n")
        print("\n\n", vr.graph_df, "\n\n")
        st.session_state.past.append(help_needed) 
        return_type_str = return_types[return_type]
        st.session_state.generated.append({'type': return_type_str, 'data': response})
        # anything but text is returned   
        if return_type in [1, 2, -1]:
            # create dummy input to fill gap where we don't need users response
            dummy_input = f'{return_type_str} received.'
            # move onto next step (don't need any input)
            response, vr.what_do_they_want, vr.graph_df, vr.data_df, return_type = generate_response(dummy_input, vr.what_do_they_want, vr.graph_df, vr.data_df)
            st.session_state.past.append(dummy_input)

            # if graph was returned again (this is possible when feedback has been given and we are at the end of the cycle)
            if return_type == 1:
                st.session_state.generated.append({'type': 'img', 'data': response})
                # move onto next step (don't need any input)
                response, vr.what_do_they_want, vr.graph_df, vr.data_df, return_type = generate_response('img received.', vr.what_do_they_want, vr.graph_df, vr.data_df)
                st.session_state.past.append(dummy_input)

            st.session_state.generated.append({'type': 'text', 'data': response})

    if st.session_state['generated']:
        for i in range(len(st.session_state['generated'])):
            # print any input from the user that is not a dummy input that we made up to fill in a blank where we don't need the users response
            if st.session_state['past'][i][-10:] != " received.":
                message(st.session_state['past'][i], is_user=True, key=str(i) + '_user', avatar_style="thumbs", seed=2225)
            if st.session_state["generated"][i]['type'] in ["text", "code"]:
                message(st.session_state["generated"][i]['data'], key=str(i), avatar_style="thumbs", seed=18)
            elif st.session_state["generated"][i]['type'] == "img":
                image = Image.open(st.session_state["generated"][i]['data'])
                st.image(image)
            elif st.session_state["generated"][i]['type'] == "table":
                data = st.session_state["generated"][i]['data']
                st.table(data)
    
    #st.button("Clear message", on_click=on_btn_click)