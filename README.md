# p4_conference
Project 4 for Udacity Full Stack Web Dev Nanodegree

Session and Speaker Design Response:
Session class is going to have the required fields of name, highlights, speaker, duration, typeOfSession, date, and start time

In the SessionForm class there are also websafe_key and websafe_conference_id fields. The websafe_key field is used to {---INSERT REASON---}. The websafe_conference_id field is used to identify which conference the session belongs to.

The two additional query types I've decided to add are finding sessions starting before or after a certain time, and sessions with duration less than or more than a certain amount. These would allow the user to plan there schedule accordingly.

If we want to run query to find sessions which are not workshops and take place before 7 pm, we would need to use two inequality filters for the query. This is however not allowed on GAE. I've decided to handle the query programmically with the backend logic. I am going to run one inequality query on the app engine, in this case the start_time filter, and then run the query result in the python code and filter out the results with session type of workshops using a for loop. Then return only those satisfy both criteria. The implementation will be the Endpoints method solvedProblematicQuery()