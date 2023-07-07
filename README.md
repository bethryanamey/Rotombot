# Rotombot
A Chatbot powered by ChatGPT that supports the automatic analysis of data. It is named after the Pokemon Rotom as it currently analyses a Pokemon dataset. 

# About
The aim of Rotombot is to explore the functionality of an "automatic analysis assistant". Users that have no knowledge of SQL or python are able to query and visualise data. ChatGPT is used to generate all necessary code. It has been coded in python and uses Streamlit for the front end. 

Here is a high level diagram of the process followed in order to generate outputs:

![alt text](https://github.com/bethryanamey/Rotombot/blob/main/README%20assets/proof%20of%20concept%20architecture.png "Process for generating output")

# Usage
## Data Summarisation or Table
You can ask Rotom to analyse data and create a summarisation or data table. Results will either be returned in a sentence (if the result only contains one row of data) or it a table structure printed in the console. Rotom will ask you how you would like to summarise the data before proceeding the write the SQL query.

Here is an example conversation:
![alt text](https://github.com/bethryanamey/Rotombot/blob/main/README%20assets/summarisation%20example.png "Example conversation for creating a summarisation.")

Once Rotom has produced a result, you can either input another question immediately, ask to see how the result was made, or ask for a graph instead. 

## Graph
You can ask Rotom to analyse the data in a visualisation. After a few prompts, the image is returned in the console. They will ask:
 - what data do you need in the visual?
 - how do you want the data visualised?
 - are there any additional customisation options?

Here is an example conversation:
![alt text](https://github.com/bethryanamey/Rotombot/blob/main/README%20assets/graph%20conversation.png "Example conversation for creating a graph.")

 And here is the result:
![alt text](https://github.com/bethryanamey/Rotombot/blob/main/README%20assets/graph%20result.png "Example graph.")

 They can also show you how the result was made and will ask you if you were happy with the result. If you are not satisified, you can detail changes so that Rotom can create a more suitable graph.

 In the example above, I go on to ask Rotom to fix the graph so that the axes labels are readable:
![alt text](https://github.com/bethryanamey/Rotombot/blob/main/README%20assets/happy.png "Rotom requesting feedback.")

And then the graph is regenerated based on my feedback:
![alt text](https://github.com/bethryanamey/Rotombot/blob/main/README%20assets/graph%20result%202.png "Reproduced graph.")

# Code
 - rotombot_streamlit.py contains the code with the back end and front end combined 
 - variables.py stores variables that rotombot updates to store important conversation information
 - requirements.txt lists all the necessary packages for making rotombot work
 - pokemon.csv is the dataset that I am using locally to run with Rotombot