import time
import re
import datetime
import urllib
import simplejson as json
from eventlet.green import urllib2

def stream(queries, queue, settings):
    def get_access_token():

        url_args = {
            'client_id' : settings.get('Facebook','app_id'),
            'client_secret' : settings.get('Facebook','app_secret'),
            'grant_type' : 'client_credentials'
        }
        url = 'https://graph.facebook.com/oauth/access_token?%s' % urllib.urlencode(url_args)

        access_token = urllib2.urlopen(url).read().split('=')[1]

        return access_token

    access_token = get_access_token()

    while True:
        for query in queries:
            url_args = {
                'access_token' : access_token,
                'batch': [
                    {
                        'method': "GET",
                        'name' : "get-user-ids",
                        "relative_url": "search?q=%s&type=post&limit=20" % 'android',
                        "omit_response_on_success": 0,
                    },
                    {
                        'method':'GET',
                        'relative_url':'/feed/?ids={result=get-user-ids:$.data.*.from.id}',
                    }
                ]
            }

            url = 'https://graph.facebook.com'
            request = urllib2.Request(url)
            request.add_data(urllib.urlencode(url_args))
            response = json.loads(urllib2.urlopen(request).read())

            profiles = json.loads(response[1]['body'])
            items = json.loads(response[0]['body'])['data']

            for item in items:
                if 'message' in item:
                    post = {
                        "service" : 'facebook',
                        "query": query,
                        "user" : {
                            "name": item['from'].get('name'),
                            "id": item['from']['id'],
                            "subscribers" : '0'
                        },
                        "links" : [],
                        "id" : item['id'],
                        "text" : item['message'],
                        #"date": str(datetime.datetime.strptime(item['created_time'], settings.get('Facebook','time_format'))),
                    }
                    url_regex = re.compile('(?:http|https|ftp):\/\/[\w\-_]+(?:\.[\w\-_]+)+(?:[\w\-\.,@?^=%&amp;:/~\+#]*[\w\-\@?^=%&amp;/~\+#])?')
                    for url in url_regex.findall(item['message']):
                        post['links'].append({ 'href' : url })
                    post['user']['avatar'] = "http://graph.facebook.com/%s/picture" % item['from']['id']
                    if 'to' in item:
                        post['to_users'] = item['to']['data']
                    if 'likes' in item:
                        post['likes'] = item['likes']['count']
                    if item['from']['id'] in profiles:
                        activity = 0
                        for profile_item in profiles[item['from']['id']]['data']:
                            activity += profile_item['comments']['count']
                            if 'likes' in profile_item:
                                activity += profile_item['likes']['count']
                        post['user']['subscribers'] = activity * 10
                        # More research needs to be done into making a more accurate multiplier
                        # what is the rough percentage of total friends someone has vs. how many
                        # actuall participate on their wall on a regular basis?
                        # We can only do our best consistant guess, as Facebook does not tell us
                        # how many friends someone has. We can only guess by activity.
                    queue.put(post)
                    time.sleep(1) # Facebook's API maxes out at 1 request/sec