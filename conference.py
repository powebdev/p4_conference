#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'


from datetime import datetime
from datetime import time

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from google.appengine.ext import db

from models import ConflictException
from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import StringMessage
from models import BooleanMessage
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForm
from models import ConferenceQueryForms
from models import TeeShirtSize
from models import Session
from models import SessionForm
from models import SessionForms
from models import SessionQueryForm
from models import SessionQueryForms
from models import Speaker
from models import SpeakerForm
from models import SpeakerForms
from models import SpeakerMiniForm

from settings import WEB_CLIENT_ID
from settings import ANDROID_CLIENT_ID
from settings import IOS_CLIENT_ID
from settings import ANDROID_AUDIENCE

from utils import getUserId

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"
MEMCACHE_FEATURED_SPEAKERS_KEY = "FEATURED_SPEAKERS"
ANNOUNCEMENT_TPL = ('Last chance to attend! The following conferences '
                    'are nearly sold out: %s')
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": ["Default", "Topic"],
}

OPERATORS = {
    'EQ':   '=',
    'GT':   '>',
    'GTEQ': '>=',
    'LT':   '<',
    'LTEQ': '<=',
    'NE':   '!='
}

FIELDS = {
    'CITY': 'city',
    'TOPIC': 'topics',
    'MONTH': 'month',
    'MAX_ATTENDEES': 'maxAttendees',
}

SESSION_FIELDS = {
    "DURATION": "duration",
    "START_TIME": "start_time",
}

CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm,
    websafeConferenceKey=messages.StringField(1),
)

SESSION_CREATE_REQUEST = endpoints.ResourceContainer(
    SessionForm,
    websafeConferenceKey=messages.StringField(1),
)

CONF_SESSION_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

CONF_SESSION_TYPE_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
    session_type=messages.StringField(2),
)

SESSION_SPEAKER_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    speaker_name=messages.StringField(1),
)

CONF_SESSION_QUERY_GET_REQUEST = endpoints.ResourceContainer(
    SessionQueryForms,
    websafeConferenceKey=messages.StringField(1),
)

SESSION_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSessionKey=messages.StringField(1),
)

SPEAKER_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSpeakerKey=messages.StringField(1),
)

SPEAKER_POST_REQUEST = endpoints.ResourceContainer(
    SpeakerMiniForm,
    websafeSpeakerKey=messages.StringField(1),
)
    
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@endpoints.api(name='conference', version='v1', audiences=[ANDROID_AUDIENCE],
               allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID,
                                   ANDROID_CLIENT_ID, IOS_CLIENT_ID],
               scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """Conference API v0.1"""

# - - - Conference objects - - - - - - - - - - - - - - - - -

    def _copyConferenceToForm(self, conf, displayName):
        """Copy relevant fields from Conference to ConferenceForm."""
        cf = ConferenceForm()
        for field in cf.all_fields():
            if hasattr(conf, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(cf, field.name, str(getattr(conf, field.name)))
                else:
                    setattr(cf, field.name, getattr(conf, field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, conf.key.urlsafe())
        if displayName:
            setattr(cf, 'organizerDisplayName', displayName)
        cf.check_initialized()
        return cf

    def _createConferenceObject(self, request):
        """Create or update Conference object, returning
        ConferenceForm/request."""
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException(
                "Conference 'name' field required")

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}
        del data['websafeKey']
        del data['organizerDisplayName']

        # add default values for those missing
        # (both data model & outbound Message)
        for df in DEFAULTS:
            if data[df] in (None, []):
                data[df] = DEFAULTS[df]
                setattr(request, df, DEFAULTS[df])

        # convert dates from strings to Date objects;
        # set month based on start_date
        if data['startDate']:
            data['startDate'] = datetime.strptime(
                data['startDate'][:10], "%Y-%m-%d").date()
            data['month'] = data['startDate'].month
        else:
            data['month'] = 0
        if data['endDate']:
            data['endDate'] = datetime.strptime(
                data['endDate'][:10], "%Y-%m-%d").date()

        # set seatsAvailable to be same as maxAttendees on creation
        if data["maxAttendees"] > 0:
            data["seatsAvailable"] = data["maxAttendees"]
        # generate Profile Key based on user ID and Conference
        # ID based on Profile key get Conference key from ID
        p_key = ndb.Key(Profile, user_id)
        c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
        c_key = ndb.Key(Conference, c_id, parent=p_key)
        data['key'] = c_key
        data['organizerUserId'] = request.organizerUserId = user_id

        # create Conference, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        Conference(**data).put()
        taskqueue.add(params={'email': user.email(),
                              'conferenceInfo': repr(request)},
                      url='/tasks/send_confirmation_email')
        return request

    @ndb.transactional()
    def _updateConferenceObject(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}

        # update existing conference
        # check that conference exists
        try:
            conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        except db.BadRequestError:
            raise endpoints.NotFoundException(
                "No conference found with key: %s"
                % request.websafeConferenceKey)

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # special handling for dates (convert string to Date)
                if field.name in ('startDate', 'endDate'):
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                    if field.name == 'startDate':
                        conf.month = data.month
                # write to Conference object
                setattr(conf, field.name, data)
        conf.put()
        prof = ndb.Key(Profile, user_id).get()
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))

    @endpoints.method(ConferenceForm, ConferenceForm, path='conference',
                      http_method='POST', name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return self._createConferenceObject(request)

    @endpoints.method(CONF_POST_REQUEST, ConferenceForm,
                      path='conference/{websafeConferenceKey}',
                      http_method='PUT', name='updateConference')
    def updateConference(self, request):
        """Update conference w/provided fields & return w/updated info."""
        return self._updateConferenceObject(request)

    @endpoints.method(CONF_GET_REQUEST, ConferenceForm,
                      path='conference/{websafeConferenceKey}',
                      http_method='GET', name='getConference')
    def getConference(self, request):
        """Return requested conference (by websafeConferenceKey)."""
        # get Conference object from request; bail if not found
        try:
            conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        except db.BadRequestError:
            raise endpoints.NotFoundException(
                'No conference found with key: %s'
                % request.websafeConferenceKey)

        prof = conf.key.parent().get()
        # return ConferenceForm
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))

    @endpoints.method(message_types.VoidMessage, ConferenceForms,
                      path='getConferencesCreated',
                      http_method='POST', name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """Return conferences created by user."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # create ancestor query for all key matches for this user
        confs = Conference.query(ancestor=ndb.Key(Profile, user_id))
        prof = ndb.Key(Profile, user_id).get()
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(
                conf, getattr(prof, 'displayName')) for conf in confs]
        )

    def _getQuery(self, request):
        """Return formatted query from the submitted filters."""
        q = Conference.query()
        inequality_filter, filters = self._formatFilters(request.filters)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Conference.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Conference.name)

        for filtr in filters:
            if filtr["field"] in ["month", "maxAttendees"]:
                filtr["value"] = int(filtr["value"])
            formatted_query = ndb.query.FilterNode(
                filtr["field"], filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q

    def _formatFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {field.name: getattr(f, field.name)
                     for field in f.all_fields()}

            try:
                filtr["field"] = FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException(
                    "Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # check if inequality operation has been used in previous
                # filters disallow the filter if inequality was performed
                # on a different field before track the field on which the
                # inequality operation is performed
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException(
                        "Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]

            formatted_filters.append(filtr)
        return (inequality_field, formatted_filters)

    @endpoints.method(ConferenceQueryForms, ConferenceForms,
                      path='queryConferences',
                      http_method='POST',
                      name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""
        conferences = self._getQuery(request)

        # need to fetch organiser displayName from profiles
        # get all keys and use get_multi for speed
        organisers = [(ndb.Key(Profile, conf.organizerUserId))
                      for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return individual ConferenceForm object per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(
                conf, names[conf.organizerUserId]) for conf in conferences])

# - - - Profile objects - - - - - - - - - - - - - - - - - - -

    def _copyProfileToForm(self, prof):
        """Copy relevant fields from Profile to ProfileForm."""
        # copy relevant fields from Profile to ProfileForm
        pf = ProfileForm()
        for field in pf.all_fields():
            if hasattr(prof, field.name):
                # convert t-shirt string to Enum; just copy others
                if field.name == 'teeShirtSize':
                    setattr(pf, field.name, getattr(
                        TeeShirtSize, getattr(prof, field.name)))
                elif field.name == "sessionKeysWishlist":
                    all_keys = []
                    for each_key in prof.sessionKeysWishlist:
                        all_keys.append(each_key.urlsafe())
                    setattr(pf, field.name, all_keys)
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        pf.check_initialized()
        return pf

    def _getProfileFromUser(self):
        """Return user Profile from datastore,
        creating new one if non-existent."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # get Profile from datastore
        user_id = getUserId(user)
        p_key = ndb.Key(Profile, user_id)
        profile = p_key.get()
        # create new Profile if not there
        if not profile:
            profile = Profile(
                key=p_key,
                displayName=user.nickname(),
                mainEmail=user.email(),
                teeShirtSize=str(TeeShirtSize.NOT_SPECIFIED),
            )
            profile.put()

        return profile      # return Profile

    def _doProfile(self, save_request=None):
        """Get user Profile and return to user, possibly updating it first."""
        # get user Profile
        prof = self._getProfileFromUser()

        # if saveProfile(), process user-modifyable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(prof, field, str(val))
                        prof.put()

        # return ProfileForm
        return self._copyProfileToForm(prof)

    @endpoints.method(message_types.VoidMessage, ProfileForm,
                      path='profile', http_method='GET', name='getProfile')
    def getProfile(self, request):
        """Return user profile."""
        return self._doProfile()

    @endpoints.method(ProfileMiniForm, ProfileForm,
                      path='profile', http_method='POST', name='saveProfile')
    def saveProfile(self, request):
        """Update & return user profile."""
        return self._doProfile(request)

# - - - Announcements - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _cacheAnnouncement():
        """Create Announcement & assign to memcache; used by
        memcache cron job & putAnnouncement().
        """
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch(projection=[Conference.name])

        if confs:
            # If there are almost sold out conferences,
            # format announcement and set it in memcache
            announcement = ANNOUNCEMENT_TPL % (
                ', '.join(conf.name for conf in confs))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

        return announcement

    @endpoints.method(message_types.VoidMessage, StringMessage,
                      path='conference/announcement/get',
                      http_method='GET', name='getAnnouncement')
    def getAnnouncement(self, request):
        """Return Announcement from memcache."""
        return StringMessage(data=memcache
                             .get(MEMCACHE_ANNOUNCEMENTS_KEY) or "")

    @staticmethod
    def _cacheFeaturedSpeaker(session_name, speaker_name):
        """Create Featured Speaker Announcement & assign to memcache.
        """
        cached_msg = "Come check out featured speaker: %s at session: %s" % (
            speaker_name, session_name,)
        memcache.set(MEMCACHE_FEATURED_SPEAKERS_KEY, cached_msg)
        return cached_msg

    @endpoints.method(message_types.VoidMessage, StringMessage,
                      path='conference/featured_speaker/get',
                      http_method='GET', name='getFeaturedSpeaker')
    def getFeaturedSpeaker(self, request):
        """Return Featured Speaker from memcache."""
        return StringMessage(data=memcache
                             .get(MEMCACHE_FEATURED_SPEAKERS_KEY) or "")

# - - - Registration - - - - - - - - - - - - - - - - - - - -

    @ndb.transactional(xg=True)
    def _conferenceRegistration(self, request, reg=True):
        """Register or unregister user for selected conference."""
        retval = None
        prof = self._getProfileFromUser()  # get user Profile

        # check if conf exists given websafeConfKey
        # get conference; check that it exists
        wsck = request.websafeConferenceKey
        try:
            conf = ndb.Key(urlsafe=wsck).get()
        except db.BadRequestError:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % wsck)

        # register
        if reg:
            # check if user already registered otherwise add
            if wsck in prof.conferenceKeysToAttend:
                raise ConflictException(
                    "You have already registered for this conference")

            # check if seats avail
            if conf.seatsAvailable <= 0:
                raise ConflictException(
                    "There are no seats available.")

            # register user, take away one seat
            prof.conferenceKeysToAttend.append(wsck)
            conf.seatsAvailable -= 1
            retval = True

        # unregister
        else:
            # check if user already registered
            if wsck in prof.conferenceKeysToAttend:

                # unregister user, add back one seat
                prof.conferenceKeysToAttend.remove(wsck)
                conf.seatsAvailable += 1
                retval = True
            else:
                retval = False

        # write things back to the datastore & return
        prof.put()
        conf.put()
        return BooleanMessage(data=retval)

    @endpoints.method(message_types.VoidMessage, ConferenceForms,
                      path='conferences/attending',
                      http_method='GET', name='getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """Get list of conferences that user has registered for."""
        prof = self._getProfileFromUser()  # get user Profile
        conf_keys = [ndb.Key(urlsafe=wsck)
                     for wsck in prof.conferenceKeysToAttend]
        conferences = ndb.get_multi(conf_keys)

        # get organizers
        organisers = [ndb.Key(Profile, conf.organizerUserId)
                      for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(
                conf, names[conf.organizerUserId]) for conf in conferences])

    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
                      path='conference/{websafeConferenceKey}',
                      http_method='POST', name='registerForConference')
    def registerForConference(self, request):
        """Register user for selected conference."""
        return self._conferenceRegistration(request)

    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
                      path='conference/{websafeConferenceKey}',
                      http_method='DELETE', name='unregisterFromConference')
    def unregisterFromConference(self, request):
        """Unregister user for selected conference."""
        return self._conferenceRegistration(request, reg=False)

    @endpoints.method(message_types.VoidMessage, ConferenceForms,
                      path='filterPlayground',
                      http_method='GET', name='filterPlayground')
    def filterPlayground(self, request):
        """Filter Playground"""
        q = Conference.query()
#        q = q.filter(Conference.city != "London")
        q = q.filter(Conference.maxAttendees == 20)
#        q = q.filter(Conference.month > 6)
        cfs = ConferenceForms()
        for conf in q:
            if conf.city != "Tokyo":
                cfs.items.append(self._copyConferenceToForm(conf, ""))
        return cfs

    def _createSpeakerObject(self, request):
        """Create Speaker object, returning SpeakerForm/request."""
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        if not request.name:
            raise endpoints.BadRequestException(
                "Speaker 'name' field required")

        # copy SpeakerForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}

        # generate Speaker Key based on system allocated Speaker ID
        speaker_id = Speaker.allocate_ids(size=1)
        speaker_key = ndb.Key(Speaker, speaker_id[0])
        data['key'] = speaker_key

        # creation of Speaker & return (modified) SpeakerForm
        Speaker(**data).put()
        return request

    def _copySpeakerToForm(self, speaker):
        """Copy relevant fields from Speaker to SpeakerForm."""
        speaker_form = SpeakerForm()
        for field in speaker_form.all_fields():
            if hasattr(speaker, field.name):
                if field.name == "sessionKeysSpeakAt":
                    all_keys = []
                    for each_key in speaker.sessionKeysSpeakAt:
                        all_keys.append(each_key.urlsafe())
                    print "%^&*(*&^%$%^&*(*&^%"
                    print all_keys
                    setattr(speaker_form, field.name, all_keys)
                else:
                    setattr(speaker_form, field.name,
                            getattr(speaker, field.name))

            elif field.name == "websafeKey":
                setattr(speaker_form, field.name, speaker.key.urlsafe())
        speaker_form.check_initialized()
        return speaker_form

    @endpoints.method(SpeakerMiniForm, SpeakerMiniForm, path='speaker',
                      http_method='POST', name='createSpeaker')
    def createSpeaker(self, request):
        """Create new speaker"""
        return self._createSpeakerObject(request)

    @endpoints.method(SPEAKER_GET_REQUEST, SpeakerForm,
                      path='speaker/{websafeSpeakerKey}',
                      http_method='GET', name='getSpeaker')
    def getSpeaker(self, request):
        """Return requested speaker (by websafeSpeakerKey)."""
        try:
            speaker = ndb.Key(urlsafe=request.websafeSpeakerKey).get()
        except db.BadRequestError:
            raise endpoints.NotFoundException(
                'No speaker found with key: %s'
                % request.websafeSpeakerKey)

        return self._copySpeakerToForm(speaker)

    @ndb.transactional()
    def _updateSpeakerObject(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # copy SpeakerForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}

        # update existing speaker
        # check that speaker exists
        try:
            speaker = ndb.Key(urlsafe=request.websafeSpeakerKey).get()
        except db.BadRequestError:
            raise endpoints.NotFoundException(
                "No speaker found with key: %s"
                % request.websafeSpeakerKey)

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # write to Speaker object
                setattr(speaker, field.name, data)
        speaker.put()
        return self._copySpeakerToForm(speaker)

    @endpoints.method(SPEAKER_POST_REQUEST, SpeakerForm,
                      path='speaker/{websafeSpeakerKey}',
                      http_method='PUT', name='updateSpeaker')
    def updateSpeaker(self, request):
        """Update speaker"""
        return self._updateSpeakerObject(request)

    @endpoints.method(message_types.VoidMessage, SpeakerForms,
                      path='allSpeaker',
                      http_method='GET', name='getAllSpeakers')
    def getAllSpeakers(self, request):
        all_speakers = Speaker.query()

        return SpeakerForms(
            items=[self._copySpeakerToForm(item) for item in all_speakers])

    def _createSessionObject(self, request):
        """Create Sessionobject, returning SessionForm/request."""
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # check if conference exists given websafeConferenceKey
        wsck = request.websafeConferenceKey
        try:
            conf = ndb.Key(urlsafe=wsck).get()
        except db.BadRequestError:
            raise endpoints.NotFoundException(
                "No conference found with key: %s "
                % request.websafeConferenceKey)

        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can add sessions to the conference.')

        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}
        del data['speaker_name']
        if data['speaker_key']:
            websafeSpeakerKey = data['speaker_key']
            try:
                speaker = ndb.Key(urlsafe=websafeSpeakerKey).get()
                data['speaker_key'] = speaker.key
            except db.BadRequestError:
                raise endpoints.NotFoundException(
                    "No speaker found with key: %s "
                    % websafeSpeakerKey)

        if data['date']:
            data['date'] = (datetime
                            .strptime(data['date'][:10], "%Y-%m-%d")
                            .date())
        if data['start_time']:
            split_time = data['start_time'].split(":")
            formatted_time = split_time[0] + ":" + split_time[1]
            data['start_time'] = (datetime
                                  .strptime(formatted_time, "%H:%M").time())
        c_key = ndb.Key(urlsafe=wsck)
        session_id = Session.allocate_ids(size=1, parent=c_key)[0]
        session_key = ndb.Key(Session, session_id, parent=c_key)
        data['key'] = session_key
        del data['websafe_key']
        del data['websafeConferenceKey']
        new_session_key = Session(**data).put()
        new_session = new_session_key.get()
        if speaker:
            if new_session_key not in speaker.sessionKeysSpeakAt:
                print "&&&&&&&&&&&&&&&" + str(new_session_key)
                speaker.sessionKeysSpeakAt.append(new_session_key)
                speaker.put()
            websafe_speaker_key = speaker.key.urlsafe()
            taskqueue.add(params={'websafe_speaker_key': websafe_speaker_key,
                                  'wsck': wsck,
                                  'session_name': data['name']},
                          url='/tasks/find_featured_speaker')
        return self._copySessionToForm(new_session)

    def _copySessionToForm(self, session_object):
        """Copy relevant fields from Session to SessionForm."""
        sf = SessionForm()
        for field in sf.all_fields():
            if hasattr(session_object, field.name):
                # convert Date/Time to date/time string; just copy others
                if field.name.endswith('date') or field.name == 'start_time':
                    setattr(sf, field.name,
                            str(getattr(session_object, field.name)))
                elif field.name == "speaker_key":
                    setattr(sf, field.name,
                            session_object.speaker_key.urlsafe())
                    speaker = session_object.speaker_key.get()
                    setattr(sf, "speaker_name", speaker.name)
                else:
                    setattr(sf, field.name,
                            getattr(session_object, field.name))
            elif field.name == "websafe_key":
                setattr(sf, field.name, session_object.key.urlsafe())
        if session_object.speaker_key:
            speaker = session_object.speaker_key.get()
            setattr(sf, 'speaker_name', speaker.name)

        sf.check_initialized()
        return sf

    @endpoints.method(SESSION_CREATE_REQUEST, SessionForm,
                      path='session',
                      http_method='POST', name='createSession')
    def createSession(self, request):
        """Create new session in given conference"""
        return self._createSessionObject(request)

    @staticmethod
    def _getConferenceSessions(wsck):
        """Return sessions belong to conference(by websafeConferenceKey)."""
        conf_sessions = Session.query(ancestor=ndb.Key(urlsafe=wsck))

        return conf_sessions

    @endpoints.method(CONF_SESSION_GET_REQUEST, SessionForms,
                      path='getConferenceSessions',
                      http_method='GET', name='getConferenceSessions')
    def getConferenceSessions(self, request):
        """Return sessions belong to conference(by websafeConferenceKey)."""
        wsck = request.websafeConferenceKey
        conf_sessions = Session.query(ancestor=ndb.Key(urlsafe=wsck))
        return SessionForms(
            items=[self._copySessionToForm(each_session)
                   for each_session in conf_sessions])

    @endpoints.method(CONF_SESSION_TYPE_GET_REQUEST, SessionForms,
                      path='getConferenceSessionsByType',
                      http_method='GET',
                      name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        """Return sessions belong to conference(by websafeConferenceKey)
        with requested session type."""
        wsck = request.websafeConferenceKey
        conf_sessions = Session.query(ancestor=ndb.Key(urlsafe=wsck))
        conf_sessions = conf_sessions.filter(
            Session.session_type == request.session_type)
        return SessionForms(
            items=[self._copySessionToForm(each_session)
                   for each_session in conf_sessions])

    @staticmethod
    def _filterSessionsBySpeaker(in_sessions, websafe_speaker_key):
        speaker = ndb.Key(urlsafe=websafe_speaker_key).get()
        filtered_sessions = in_sessions.filter(
            Session.speaker_key == speaker.key)
        return (filtered_sessions, speaker.name)

    @endpoints.method(SPEAKER_GET_REQUEST, SessionForms,
                      path='getSessionsBySpeaker',
                      http_method='GET',
                      name='getSessionsBySpeaker')
    def getSessionsBySpeaker(self, request):
        """Return sessions by a given speaker"""
        try:
            speaker = ndb.Key(urlsafe=request.websafeSpeakerKey).get()
        except db.BadRequestError:
            raise endpoints.NotFoundException(
                "No speaker found with key: %s "
                % request.websafeSpeakerKey)

        sessions_with_speaker = ndb.get_multi(speaker.sessionKeysSpeakAt)

        # return set of SessionForm objects per Session
        return SessionForms(
            items=[self._copySessionToForm(each_session)
                   for each_session in sessions_with_speaker])

    def _alterWishlist(self, request, add=True):
        """Add or remove sessions fromo wishlist."""
        retval = None
        prof = self._getProfileFromUser()  # get user Profile

        # check if session exists given websafeSessionKey

        try:
            session_key = ndb.Key(urlsafe=request.websafeSessionKey)
        except db.BadRequestError:
            raise endpoints.NotFoundException(
                "No session found with key: %s " % request.websafeSessionKey)

        # add to wishlist
        if add:
            # check if session already in user's wishlist
            if session_key in prof.sessionKeysWishlist:
                raise ConflictException(
                    "Session already in your wishlist")

            # add session to wishlist
            prof.sessionKeysWishlist.append(session_key)
            retval = True

        # remove from wishlist
        else:
            # check if session already in user's wishlist
            if session_key in prof.sessionKeysWishlist:

                # remove session from wishlist
                prof.sessionKeysWishlist.remove(session_key)
                retval = True
            else:
                retval = False

        # write things back to the datastore & return
        prof.put()
        return BooleanMessage(data=retval)

    @endpoints.method(SESSION_GET_REQUEST, BooleanMessage,
                      path='session/wishlist/{websafeSessionKey}',
                      http_method='POST',
                      name='addSessionToWishlist')
    def addSessionToWishlist(self, request):
        """Add session to wishlist"""
        return self._alterWishlist(request)

    @endpoints.method(SESSION_GET_REQUEST, BooleanMessage,
                      path='session/wishlist/{websafeSessionKey}',
                      http_method='DELETE',
                      name='deleteSessionInWishlist')
    def deleteSessionInWishlist(self, request):
        """Remove session from wishlist"""
        return self._alterWishlist(request, add=False)

    @endpoints.method(message_types.VoidMessage, SessionForms,
                      path='session/wishlist',
                      http_method='GET',
                      name='getSessionsInWishlist')
    def getSessionsInWishlist(self, request):
        """Get list of session that user has added to wishlist."""
        prof = self._getProfileFromUser()  # get user Profile
        conf_sessions = ndb.get_multi(prof.sessionKeysWishlist)

        # return set of SessionForm objects per Session
        return SessionForms(
            items=[self._copySessionToForm(conf_session)
                   for conf_session in conf_sessions])

    def _getSessionQuery(self, request):
        """Return formatted query from the submitted filters."""
        wsck = request.websafeConferenceKey
        conf_sessions = Session.query(ancestor=ndb.Key(urlsafe=wsck))
        inequality_filter, filters = (self
                                      ._formatSessionFilters(request.filters))

        # If exists, sort on inequality filter first
        if not inequality_filter:
            conf_sessions = conf_sessions.order(Session.start_time)
        else:
            conf_sessions = conf_sessions.order(
                ndb.GenericProperty(inequality_filter))
            conf_sessions = conf_sessions.order(Session.start_time)

        for filtr in filters:
            if filtr["field"] == "duration":
                filtr["value"] = int(filtr["value"])
            # processing start_time query
            elif filtr["field"] == "start_time":
                # when performing query on either DateProperty or TimeProperty
                # in datastore, the datatype datetime is required (as opposing
                # to the correspodning python datatype date and time). The
                # following code segment convert the time string to proper
                # datetime object for query operation. The date 1970-01-01 is
                # used due to the fact datastore store that particular date to
                # the value in TimeProperty
                split_time = filtr["value"].split(":")
                formatted_time = (
                    "1970-01-01 " + split_time[0] + ":" + split_time[1])
                filtr["value"] = (datetime
                                  .strptime(formatted_time, "%Y-%m-%d %H:%M"))
            formatted_query = ndb.query.FilterNode(
                filtr["field"], filtr["operator"], filtr["value"])
            print filtr["field"] + filtr["operator"] + str(filtr["value"])
            try:
                conf_sessions = conf_sessions.filter(formatted_query)
                print conf_sessions.count()
            except:
                raise endpoints.BadRequestException(
                    "Bad query operation.")
        return conf_sessions

    def _formatSessionFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {field.name: getattr(f, field.name)
                     for field in f.all_fields()}

            try:
                filtr["field"] = SESSION_FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException(
                    "Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # check if inequality operation has been used in previous
                # filters disallow the filter if inequality was performed
                # on a different field before track the field on which the
                # inequality operation is performed
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException(
                        "Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]

            formatted_filters.append(filtr)
        return (inequality_field, formatted_filters)

    @endpoints.method(CONF_SESSION_QUERY_GET_REQUEST, SessionForms,
                      path='querySession',
                      http_method='POST',
                      name='querySession')
    def querySession(self, request):
        """Query for sessions"""
        conf_sessions = self._getSessionQuery(request)

        # return individual ConferenceForm object per Conference
        return SessionForms(
            items=[self._copySessionToForm(one_session)
                   for one_session in conf_sessions])

    @endpoints.method(message_types.VoidMessage, SessionForms,
                      path='solvedProblematicQuery',
                      http_method='GET',
                      name='solvedProblematicQuery')
    def solvedProblematicQuery(self, request):
        """ Implementation of proposed solution for problematic query in Task 3.
        """
        all_sessions = Session.query()
        all_sessions = (all_sessions
                        .filter(Session.start_time < time(19, 00))
                        .order(Session.start_time))
        sfs = SessionForms()
        for item in all_sessions:
            if item.session_type != "workshops":
                sfs.items.append(self._copySessionToForm(item))
        return sfs

api = endpoints.api_server([ConferenceApi])  # register API
