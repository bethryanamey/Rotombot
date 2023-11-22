#!/usr/bin/python3
import pandas as pd

schema = 'pokemon_public'

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