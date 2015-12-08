# p4_conference
Project 4 for Udacity Full Stack Web Dev Nanodegree

Session and Speaker Design Response:
Session class is going to have fields of:
name(required field): String type, names are bunch texts
highlights: String type, highlights are bunch texts
speaker_id: String type, urlsafe id for speaker entities which are bunch texts
speaker_name: String type, names are bunch texts
duration: Integer type, duration of the session in minutes, integer type allow inequality querying to find sessions which are over or under certain dutation
session_type: String type, type of session, bunch of texts
date: Date type, this corresponds to the Pythono date class.
start_time: String type, the starting time of the session in 24 hr format ie. hh:mm. 7pm -> 19:00 and 9:30am -> 09:30

In the SessionForm class there are also websafe_key field which is a text string which can be used to access session objects easily.

The session speakers are going to implemented as entities which are saved in the datastore. To start out the Speaker kind only has one field which contains the name of the speaker, but it can be expanded in the future and accommendates more detailed information about the speaker much like the Profile kind does.

Session is created as child of Conference, this allows user to perform query by kind filter by ancestor to retrieve sessions belong to one conference.

The two additional query types I've decided to add are finding sessions starting before or after a certain time, and sessions with duration less than or more than a certain amount. These would allow the user to plan there schedule accordingly.
The additional queries propsoed are handled in one single Endpoints method querySessions(). User can use filters to perform the desired query much like the queryConfrences() Endpoints method.

If we want to run query to find sessions which are not workshops and take place before 7 pm, we would need to use two inequality filters for the query. This is however not allowed on GAE. I've decided to handle the query programmically with the backend logic. I am going to run one inequality query on the app engine, in this case the start_time filter, and then run the query result in the python code and filter out the results with session type of workshops using a for loop. Then return only those satisfy both criteria. The implementation will be the Endpoints method solvedProblematicQuery()