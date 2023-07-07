import pandas as pd

matching_phrases = {    
    # visualise/show/draw this in a graph
    'visualise': [r'.*[visualise|show|draw|present] this in a graph.*'],
    'graph': [r'.*graph.*', r'.*visual.*'], 
    'data': [r'.*table.*', r'.*summarisation.*', r'.*aggregate.*'],
    'rotom': [r'.*[learn|know].*about rotom.*'],
    # show me the code please, how was this summarisation made, what code was used to make this
    'code': [r'.*show.*code*', r'.*how.*made*', r'.*what.*code*']
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
    [2, "messages", None, False, None],
    [2, "gpt_response", None, False, None],
    [3, "show_work", "Do you want to see how the result was made? Yes or No", False, None],
    [3, "happy", "Were you happy with the result? Yes or No", False, None],
    # if we are populating this variable, empty dataframe
    [4, "graph_end", "Great, glad I could help! Would you like to produce another graph or a data table/summarisation?", False, None],
    [5, "problem", "Was it a problem with the data or graph? Enter 'data', 'graph', or 'both'. Enter nothing if you want the program to try again with the previous prompts", False, None],
    # if data_changes, prompt to automate_visualisation will be data_required + data_changes    
    [6, "previous_messages", None, False, None],
    [6, "previous_response", None, False, None],
    [6, "data_changes", "What would you like to change about the data? Write a prompt to add to your initial input. Enter nothing if you want the program to try again with the previous prompts", False, None],
    [6, "visual_changes", "What would you like to see different in the graph? Write a prompt to add to your initial input. Enter nothing if you want the program to try again with the previous prompts", False, None]
], columns=["stage", "variable", "prompt", "completed", "input"])

# table saving prompts inputs so that the program can call upon them later
data_df = pd.DataFrame([
    [1, 'user_request',"Please describe the data table/summarisation you would like to create\n", False, None],
    [2, 'SQL_query', None, False, None],
    [2, 'messages', None, False, None],
    [2, 'result', None, False, None]
], columns=["stage", "variable", "prompt", "completed", "input"])