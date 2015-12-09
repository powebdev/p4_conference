<h1>p4_conference</h1>
Project 4 for Udacity Full Stack Web Dev Nanodegree</br>
Project ID: project-4-conference-app-1152</br>
<a href="https://project-4-conference-app-1152.appspot.com/">Deployed App</a></br>
<a href="https://project-4-conference-app-1152.appspot.com/_ah/api/explorer">API Explorer Link</a></br>

<h2>Exceeds Spec Criteria</h2>
<ul>Implemented entity for speakers</ul>
<ul>Speaker entity can be expanded with more information of the speaker</ul>
<ul>Implemented proposed solution for problematic query in task 3</ul>

<h2>Session and Speaker Design Response:</h2>
<p>Session class is going to have fields of:
<ul>name(required field): String type, names are bunch texts</ul>
<ul>highlights: String type, highlights are bunch texts</ul>
<ul>speaker_id: String type, urlsafe id for speaker entities which are bunch texts</ul>
<ul>speaker_name: String type, names are bunch texts</ul>
<ul>duration: Integer type, duration of the session in minutes, integer type allow inequality querying to find sessions which are over or under certain dutation</ul>
<ul>session_type: String type, type of session, bunch of texts</ul>
<ul>date: Date type, this corresponds to the Pythono date class.</ul>
<ul>start_time: String type, the starting time of the session in 24 hr format ie. hh:mm. 7pm -> 19:00 and 9:30am -> 09:30</ul>
</p>
<p>In the SessionForm class there are also websafe_key field which is a text string which can be used to access session objects easily.</p>

<p>The session speakers are going to be implemented as entities which are saved in the datastore. To start out the Speaker kind only has one field which contains the name of the speaker, but it can be expanded in the future and accommendates more detailed information about the speaker much like the Profile kind does.</p>

<p>Session is created as child of Conference, this allows user to perform query by kind filter by ancestor to retrieve sessions belong to one conference.</p>

<h2>Task 3: Additional Queries</h2>
<p>The two additional query types I've decided to add are finding sessions starting before or after a certain time, and sessions with duration less than or more than a certain amount. These would allow the user to plan there schedule accordingly.</p>
<p>The additional queries propsoed are handled in one single Endpoints method <b>querySessions()</b>. User can use filters to perform the desired query much like the <b>queryConfrences()</b> Endpoints method.</p>

<h2>Task 3: Query Problem</h2>
<p>If we want to run query to find sessions which are not workshops and take place before 7 pm, we would need to use two inequality filters for the query. This is however not allowed on GAE.</p>
<p>I've decided to handle the query programmically with the backend logic. I am going to run one inequality query on the app engine, in this case the start_time filter, and then run the query result in the python code and filter out the results with session type of workshops using a for loop. Then return only those satisfy both criteria.</p>
<p>The implementation will be the Endpoints method <b>solvedProblematicQuery()</b></p>
