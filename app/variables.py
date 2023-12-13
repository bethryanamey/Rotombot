#!/usr/bin/python3
import pandas as pd

# change this variable to point to different dataset
chosen_data_source = 'confirm_data_lake'

data_connections = {
    # information on pokemon data in data lake
    "pokemon_data_lake":{
        'friendly_name':"Pokemon",
        'data_store':"data_lake_mi_dev",
        'database':'public',
        'schema':'pokemon_public',
        'db_context':'\n There are two tables that contain information on Pokemon. Types in the pokemon table have been encoded. The meaningful values of the types are in the type_ids table.',
        'demo_question':'How many water type pokemon are heavier than Pikachu?',
        'demo_answer':"SELECT COUNT(*) FROM pokemon_public.pokemon WHERE type1_id = (SELECT type_id FROM dbo.type_ids WHERE type = 'Water') AND weight_kg > (SELECT weight_kg FROM dbo.pokemon WHERE name = 'Pikachu');"
    },

    # information on STATS19 data in data lake
    "STATS19_data_lake":{
        'friendly_name':"STATS19",
        'data_store':"data_lake_mi_dev",
        'database':'public',
        'schema':'stats19_public_roadsafety',
        'db_context':"\nSeveral fields across the accidents, casualty, and vehicle tables include values that are encoded such as local_authority_highway and road_type. Therefore, the value-lookup table is used to convert the encoded values to meaningful content. The lookup table is used by finding the relevant field from the encoded table in the field name column in the lookup, finding the encoded value in the code form column, and then the meaningful value that we need is in the label column.",
        'demo_question':"How many accidents happened in Essex between 2016 and 2020 inclusive?",
        'demo_answer':"SELECT COUNT(*) FROM [stats19_public_roadsafety].[accidents] WHERE accident_year BETWEEN 2016 AND 2020 AND local_authority_highway IN (SELECT [code_format] FROM [stats19_public_roadsafety].[value-lookup] vl WHERE vl.[table] = 'Accident' AND vl.field_name = 'local_authority_highway' AND vl.label = 'Essex');"
    },

    # information on pokemon data in Azure SQL Server
    "pokemon_sql_server":{
        'friendly_name':"Pokemon",
        'data_store':"azure_sql_server",
        'database':'rotom-db',
        'schema':'dbo',
        'db_context':'\n There are two tables that contain information on Pokemon. Types in the pokemon table have been encoded. The meaningful values of the types are in the type_ids table.',
        'demo_question':'How many water type pokemon are heavier than Pikachu?',
        'demo_answer':"SELECT COUNT(*) FROM dbo.pokemon WHERE type1_id = (SELECT type_id FROM dbo.type_ids WHERE type = 'Water') AND weight_kg > (SELECT weight_kg FROM dbo.pokemon WHERE name = 'Pikachu');"
    },

    # information on confirm data in data lake (temporary access)
    "confirm_data_lake":{
        'friendly_name':"Confirm",
        'data_store':"data_lake_mi_dev",
        'database':'bronze-scientist',
        'schema':"confirm_bronze_scientist_trafford",
        'db_context':"\nThis database contains information on scheduled, ongoing, and completed work. The jobs table details information about work to be/being completed. Some jobs in the jobs table may have several rows. This is because a new row is added whenever the job is updated (rather than updating the previous row of data). Therefore, to find the latest row of information regarding a job, you need to find the largest currentLogNumber out of all the available rows. This is particularly important if we are querying the frequency of jobs. Dates are strings in the format 'yyyy-mm-ddThh:mm:ss'. Columns with True or False values use strings of the form 'Y' or 'N' respectively. The JobStatusLogs table includes updates on the job (i.e. when the status of a job changed and to what status). The jobStatuses table can be used to convert the meaningless ID of a status to a more meaningful value (joining on code). There are some issues with duplicates in the jobStatuses table so you may need to use aggregates (e.g. MAX) to find a singular value, for example, if we needed the status of one job. The priorities table can be used to decode the priority code in the jobs table and to provide more information on different levels of priority. The centralSites table contains information on the locations of work. The site code in the jobs table joins to the code in the central sites table.",
        'demo_question':'What is the job status of job with number 777454?',
        'demo_answer':"SELECT MAX(js.name) AS [jobStatus] FROM [confirm_bronze_scientist_trafford].[jobStatusLogs] jsl INNER JOIN [confirm_bronze_scientist_trafford].[jobStatuses] js ON jsl.statusCode = js.code WHERE jobNumber = '777454.0' AND loggedDate = (SELECT MAX(loggedDate) FROM [confirm_bronze_scientist_trafford].[jobStatusLogs] WHERE jobNumber = '777454.0');"
    },

    # information on confirm data in data lake (temporary access)
    "bmsi_data_lake":{
        'friendly_name':"BMSI",
        'data_store':"data_lake_mi_prod",
        'database':'bmsi-silver',
        'schema':"bmsi-silver",
        'db_context':"\nThis database contains information on meter readings at several different sites. Each customer can be responsible for multiple sites. A description of the meter reading is in the HistoryDescription column and the ID columns can be used to link the meter reading type with the site and the time of the reading. The value of the meter reading is in the value column. Information about that value is in the ValueFacets column.",
        'demo_question':'',
        'demo_answer':""
    }
}

matching_phrases = {    
    # visualise/show/draw this in a graph
    'visualise': [r'.*[visualise|show|draw|present] this in a graph.*'],
    'graph': [r'.*graph.*', r'.*visual.*'], 
    'data': [r'.*table.*', r'.*summarisation.*', r'.*aggregate.*'],
    'rotom': [r'.*[learn|know].*about rotom.*', r'.*[who|what].*rotom*'],
    # show me the code please, how was this summarisation made, what code was used to make this
    'code': [r'.*show.*code*', r'.*how.*made*', r'.*what.*code*'],
    # this didn't work, this didnt work, there was a problem, this isnt right, this isn't right, this is not right
    'problem': [r".*did(n'?| no)t.*work*", r'.*problem.*', r".*(isn'?t|is not).*right*"]
}
negative_responses = ["nothing", "don't", "stop", "sorry"]
exit_commands = ["quit", "pause", "exit", "goodbye", "bye", "later", "stop"]

# these variables will be updated as the conversation progresses

# saves the choice the user made earlier in the conversation (graph, table, or rotom)
what_do_they_want = None

# list of all plots made in case we design more than one
plots = []

# table saving prompts inputs so that the program can call upon them later
graph_df = pd.DataFrame([
    [1, 'data_required',"Please describe the data you would like in the visual", False, None],
    [1, 'visualisation_description', "Please describe how you would like this data to be visualised (i.e. plot type and axis variables)", False, None],
    [1, 'customisation_options',"Is there anything else you would like to customise on the graph? Enter 'no' if not", False, None],
    # results from automate_visualtion (no prompt needed)
    [2, "SQL_query", None, False, None],
    [2, "plotting_code", None, False, None],
    [2, "SQL_messages", None, False, None],
    [2, "python_messages", None, False, None],
    [2, "SQL_gpt_response", None, False, None],
    [2, "python_gpt_response", None, False, None],
    [3, "show_work", "Do you want to see how the result was made? Yes or No", False, None],
    [3, "happy", "Were you happy with the result? Yes or No", False, None],
    # if we are populating this variable, empty dataframe
    [4, "graph_end", "Great, glad I could help! Would you like to produce another graph or a data table/summarisation?", False, None],
    [5, "problem", "Was it a problem with the data or graph? Enter 'data', 'graph', or 'both'. Enter nothing if you want the program to try again with the previous prompts", False, None],
    # if data_changes, prompt to automate_visualisation will be data_required + data_changes    
    [6, "previous_SQL_messages", None, False, None],
    [6, "previous_python_messages", None, False, None],
    [6, "previous_SQL_gpt_response", None, False, None],
    [6, "previous_python_gpt_response", None, False, None],
    [7, "data_changes", "What would you like to change about the data? Write a prompt to add to your initial input. Enter nothing if you want the program to try again with the previous prompts", False, None],
    [7, "visual_changes", "What would you like to see different in the graph? Write a prompt to add to your initial input. Enter nothing if you want the program to try again with the previous prompts", False, None]
], columns=["stage", "variable", "prompt", "completed", "input"])

#TODO: use dict instead of df
graph_dict = {
    1:{
        "stage":1, 
        "variable":'data_required', 
        "prompt":"Please describe the data you would like in the visual", 
        "completed":False, 
        "input":None
    },
    2:{
        "stage":1, 
        "variable":'visualisation_description', 
        "prompt":"Please describe how you would like this data to be visualised (i.e. plot type and axis variables)", 
        "completed":False, 
        "input":None
    },
    3:{
        "stage":1, 
        "variable":'customisation_options', 
        "prompt":"Is there anything else you would like to customise on the graph? Enter 'no' if not", 
        "completed":False, 
        "input":None
    },
    # results from automate_visualtion (no prompt needed)
    4:{
        "stage":2, 
        "variable":"SQL_query", 
        "prompt":None, 
        "completed":False, 
        "input":None
    },
    5:{
        "stage":2, 
        "variable":"plotting_code", 
        "prompt":None, 
        "completed":False, 
        "input":None},
    6:{
        "stage":2, 
        "variable":"messages", 
        "prompt":None, 
        "completed":False, 
        "input":None
    },
    7:{
        "stage":2, 
        "variable":"gpt_response", 
        "prompt":None, 
        "completed":False, 
        "input":None
    },
    8:{
        "stage":3, 
        "variable":"show_work", 
        "prompt":"Do you want to see how the result was made? Yes or No", 
        "completed":False, 
        "input":None
    },
    9:{
        "stage":3, 
        "variable":"happy", 
        "prompt":"Were you happy with the result? Yes or No", 
        "completed":False, 
        "input":None
    },
    # if we are populating this variable, empty dataframe
    10:{
        "stage":4, 
        "variable":"graph_end", 
        "prompt":"Great, glad I could help! Would you like to produce another graph or a data table/summarisation?", 
        "completed":False, 
        "input":None
    },
    11:{
        "stage":5, 
        "variable":"problem", 
        "prompt":"Was it a problem with the data or graph? Enter 'data', 'graph', or 'both'. Enter nothing if you want the program to try again with the previous prompts", 
        "completed":False, 
        "input":None
    },
    # if data_changes, prompt to automate_visualisation will be data_required + data_changes    
    12:{
        "stage":6, 
        "variable":"previous_messages", 
        "prompt":None, 
        "completed":False, 
        "input":None
    },
    13:{
        "stage":6, 
        "variable":"previous_response", 
        "prompt":None, 
        "completed":False, 
        "input":None
    },
    14:{
        "stage":6, "variable":"data_changes", 
        "prompt":"What would you like to change about the data? Write a prompt to add to your initial input. Enter nothing if you want the program to try again with the previous prompts", 
        "completed":False, 
        "input":None
    },
    15:{
        "stage":6, 
        "variable":"visual_changes", 
        "prompt":"What would you like to see different in the graph? Write a prompt to add to your initial input. Enter nothing if you want the program to try again with the previous prompts", 
        "completed":False, 
        "input":None
    }
}

# table saving prompts inputs so that the program can call upon them later
data_df = pd.DataFrame([
    [1, 'user_request',"Please describe the data table/summarisation you would like to create\n", False, None],
    [2, 'SQL_query', None, False, None],
    [2, 'messages', None, False, None],
    [2, 'result', None, False, None],
    [3, "previous_messages", None, False, None],
    [3, "previous_response", None, False, None],
    [4, "data_changes", "What would you like to change about the data?", False, None],
], columns=["stage", "variable", "prompt", "completed", "input"])