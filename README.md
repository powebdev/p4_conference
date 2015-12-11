#p4_conference
Project 4 for Udacity Full Stack Web Dev Nanodegree</br>
Project ID: project-4-conference-app-1152</br>
<a href="https://project-4-conference-app-1152.appspot.com/">Deployed App</a></br>
<a href="https://project-4-conference-app-1152.appspot.com/_ah/api/explorer">API Explorer Link</a></br>

## Products
- [App Engine][1]

## Language
- [Python 2.x][2]

## APIs
- [Google Cloud Endpoints][3]

## Setup Instructions
1. Confirm the value of `application` in `app.yaml` to __project-4-conference-app-1152__
1. Confirm the values at the top of `settings.py` to
   reflect the respective client IDs you have registered in the
   [Developer Console][4].
1. Update the value of CLIENT_ID in `static/js/app.js` to the Web client ID
1. (Optional) Mark the configuration files as unchanged as follows:
   `$ git update-index --assume-unchanged app.yaml settings.py static/js/app.js`
1. Run the app with the devserver using `dev_appserver.py DIR`, and ensure it's running by visiting your local server's address (by default [localhost:8080][5].)
1. (Optional) Generate your client library(ies) with [the endpoints tool][6].
1. Deploy your application.

##Exceeds Spec Criteria
* Implemented entity for speakers
* Speaker entity can be expanded with more information of the speaker
* Implemented proposed solution for problematic query in task 3

##Session and Speaker Design Response:
Session class is going to have fields of:
* name(required field): String type, names are bunch texts
* highlights: String type, highlights are bunch texts
* speaker_id: String type, urlsafe id for speaker entities which are bunch texts
* speaker_name: String type, names are bunch texts
* duration: Integer type, duration of the session in minutes, integer type allow inequality querying to find sessions which are over or under certain dutation
* session_type: String type, type of session, bunch of texts
* date: Date type, this corresponds to the Pythono date class
* start_time: String type, the starting time of the session in 24 hr format ie. hh:mm. 7pm -> 19:00 and 9:30am -> 09:30

In the SessionForm class there are also websafe_key field which is a text string which can be used to access session objects easily.

The session speakers are going to be implemented as entities which are saved in the datastore. To start out the Speaker kind only has one field which contains the name of the speaker, but it can be expanded in the future and accommendates more detailed information about the speaker much like the Profile kind does.

Session is created as child of Conference, this allows user to perform query by kind filter by ancestor to retrieve sessions belong to one conference.

##Task 3: Additional Queries
The two additional query types I've decided to add are finding sessions starting before or after a certain time, and sessions with duration less than or more than a certain amount. These would allow the user to plan there schedule accordingly.

The additional queries propsoed are handled in one single Endpoints method __querySessions()__. User can use filters to perform the desired query much like the <b>queryConfrences()</b> Endpoints method.

##Task 3: Query Problem
If we want to run query to find sessions which are not workshops and take place before 7 pm, we would need to use two inequality filters for the query. This is however not allowed on GAE.

I've decided to handle the query programmically with the backend logic. I am going to run one inequality query on the app engine, in this case the start_time filter, and then run the query result in the python code and filter out the results with session type of workshops using a for loop. Then return only those satisfy both criteria.

The implementation will be the Endpoints method __solvedProblematicQuery()__

[1]: https://developers.google.com/appengine
[2]: http://python.org
[3]: https://developers.google.com/appengine/docs/python/endpoints/
[4]: https://console.developers.google.com/
[5]: https://localhost:8080/
[6]: https://developers.google.com/appengine/docs/python/endpoints/endpoints_tool
