#!/usr/bin/python3

# Usage example:
# python captions.py --videoid='<video_id>' --name='<name>' --file='<file>' --language='<language>' --action='action'

import httplib2, os, sys, re, datetime

from googleapiclient.discovery import build_from_document
from googleapiclient.errors import HttpError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

import logging
logging.basicConfig()

def get_isosplit(s, split):
    if split in s:
        n, s = s.split(split)
    else:
        n = 0
    return n, s

# https://stackoverflow.com/a/64232786/3682277
def parse_isoduration(s):
    """Helper function for parsing video durations"""
    # Remove prefix
    s = s.split('P')[-1]

    # Step through letter dividers
    days, s = get_isosplit(s, 'D')
    _, s = get_isosplit(s, 'T')
    hours, s = get_isosplit(s, 'H')
    minutes, s = get_isosplit(s, 'M')
    seconds, s = get_isosplit(s, 'S')

    # Convert all to seconds
    dt = datetime.timedelta(days=int(days), hours=int(hours), minutes=int(minutes), seconds=int(seconds))
    return int(dt.total_seconds())

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret. You can acquire an OAuth 2.0 client ID and client secret from
# the {{ Google Dev Console }} at
# {{ https://console.developers.google.com/ }}.
# Please ensure that you have enabled the YouTube Data API for your project.
# For more information about using OAuth2 to access the YouTube Data API, see:
#   https://developers.google.com/youtube/v3/guides/authentication
# For more information about the client_secrets.json file format, see:
#   https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
SECRETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../SECRETS"))

CLIENT_SECRETS_FILE = "%s/google_client_secrets.json" % (SECRETS_DIR)

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account and requires requests to use an SSL connection.
YOUTUBE_READ_WRITE_SSL_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# This variable defines a message to display if the CLIENT_SECRETS_FILE is
# missing.
MISSING_CLIENT_SECRETS_MESSAGE = """
WARNING: Please configure OAuth 2.0
To make this sample run you will need to populate the client_secrets.json file
found at:
   %s
with information from the APIs Console
https://console.developers.google.com
For more information about the client_secrets.json file format, please visit:
https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
""" % os.path.abspath(os.path.join(os.path.dirname(__file__),
                                   CLIENT_SECRETS_FILE))

# Authorize the request and store authorization credentials.
def get_authenticated_service(args):
  flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE, scope=YOUTUBE_READ_WRITE_SSL_SCOPE,
    message=MISSING_CLIENT_SECRETS_MESSAGE)

  # The credentials will be saved to this file,
  # so we need to sign in only once
  storage = Storage("%s/%s-oauth2.json" % (SECRETS_DIR, os.path.basename(sys.argv[0])))
  credentials = storage.get()

  if credentials is None or credentials.invalid:
    credentials = run_flow(flow, storage, args)

  # https://stackoverflow.com/questions/29762529/where-can-i-find-the-youtube-v3-api-captions-json-discovery-document
  with open("%s/youtube-v3-api-captions.json" % os.path.dirname(__file__), "r", encoding = "utf-8") as f:
    doc = f.read()
    return build_from_document(doc, http=credentials.authorize(httplib2.Http()))


# Call the API's captions.list method to list the existing caption tracks.
def list_captions(youtube, video_id, verbose=True):
  results = youtube.captions().list(
    part="snippet",
    videoId=video_id
  ).execute()

  for item in results["items"]:
    id = item["id"]
    name = item["snippet"]["name"]
    language = item["snippet"]["language"]
    if verbose:
        print("Caption track '%s(%s)' in '%s' language." % (name, id, language))

  return results["items"]


# Call the API's captions.insert method to upload a caption track in draft status.
def upload_caption(youtube, video_id, language, name, is_draft, file):
  try:
    insert_result = youtube.captions().insert(
    part="snippet",
    body=dict(
      snippet=dict(
        videoId=video_id,
        language=language,
        name=name,
        isDraft=is_draft
      ),
    ),
    media_mime_type = 'text/xml',
    media_body = file,
    ).execute()
  except HttpError as e:
      print("Got the following error during sub upload, YTID = ", video_id)
      print(e)
      raise

  id = insert_result["id"]
  name = insert_result["snippet"]["name"]
  language = insert_result["snippet"]["language"]
  status = insert_result["snippet"]["status"]
  print("Uploaded caption track '%s(%s) in '%s' language, '%s' status." % (name,
      id, language, status) )
  return True


# Call the API's captions.update method to update an existing caption track's draft status
# and publish it. If a new binary file is present, update the track with the file as well.
def update_caption(youtube, video_id, language, caption_id, is_draft, file):
  try:
    update_result = youtube.captions().update(
    part="snippet",
    body=dict(
      id=caption_id,
      snippet=dict(
        isDraft=is_draft
      )
    ),
    media_mime_type = 'text/xml',
    media_body=file
    ).execute()

  except HttpError as e:
      print("Got the following error during subtitle update")
      print(e)
      raise

  name = update_result["snippet"]["name"]
  isDraft = update_result["snippet"]["isDraft"]
  print("Updated caption track '%s' draft status to be: '%s'" % (name, isDraft))
  if file:
    print("and updated the track with the new uploaded file.")

  return True


# Call the API's captions.download method to download an existing caption track.
def download_caption(youtube, caption_id, tfmt):
  subtitle = youtube.captions().download(
    id=caption_id,
    tfmt=tfmt
  ).execute()

  #print("First line of caption track: %s" % (subtitle))
  with open(caption_id, "wb") as f:
      f.write(subtitle)

# Get API information about a YT video
def list_video(youtube, ytid):
    """https://developers.google.com/youtube/v3/docs/videos/list"""
    response = youtube.videos().list(
	part='snippet',
	id=ytid).execute()
    snippet = response['items'][0]['snippet']
    for key in snippet.keys():
        print(key)
        print(snippet[key])
    return snippet

# Print video duration (seconds)
def video_duration(youtube, ytid):
    """https://developers.google.com/youtube/v3/docs/videos/list"""
    response = youtube.videos().list(
	part='contentDetails',
	id=ytid).execute()
    iso_duration = response['items'][0]['contentDetails']['duration']
    duration = parse_isoduration(iso_duration)
    print(ytid, duration)
    return duration

if __name__ == "__main__":
  # The "videoid" option specifies the YouTube video ID that uniquely
  # identifies the video for which the caption track will be uploaded.
  argparser.add_argument("--videoid",
    help="Required; ID for video for which the caption track will be uploaded.")
  argparser.add_argument("--videoids-file",
    help="Input file with one ID per row.")
  # The "name" option specifies the name of the caption trackto be used.
  argparser.add_argument("--name", help="Caption track name", default="")
  # The "file" option specifies the binary file to be uploaded as a caption track.
  argparser.add_argument("--file", help="Captions track file to upload")
  # The "language" option specifies the language of the caption track to be uploaded.
  argparser.add_argument("--language", help="Caption track language", default="en")
  # The "captionid" option specifies the ID of the caption track to be processed.
  argparser.add_argument("--captionid", help="Required; ID of the caption track to be processed")
  # The "action" option specifies the action to be processed.
  argparser.add_argument("--action", help="Action: list|list_video|upload|update|download")
  # The "action" option specifies the action to be processed.
  argparser.add_argument("--draft", help="Publish subtitles?", default=False, action='store_true')


  args = argparser.parse_args()
  SUPPORTED_ACTIONS = ('upload', 'download', 'update', 'list', 'list_video',
          'video_duration')

  if args.action not in SUPPORTED_ACTIONS:
      print("Available actions:", SUPPORTED_ACTIONS)
      exit("Unsupported action = %s" % args.action)

  if (args.action in ('upload', 'list', 'list_video', 'video_duration')):
    if not args.videoid and not args.videoids_file:
          exit("Please specify videoid using the --videoid= parameter.")
    if args.videoid and args.videoids_file:
        exit("Incompatible options --videoid and --videoids-file.")

  if (args.action in ('update', 'download', 'delete')):
    if not args.captionid:
          exit("Please specify captionid using the --captionid= parameter.")

  if args.action == 'upload':
    if not args.file:
      exit("Please specify a caption track file using the --file= parameter.")
    if not os.path.exists(args.file):
      exit("Please specify a valid file using the --file= parameter.")

  if args.action in ('upload', 'update', 'delete'):
      # NOTE(danielhollas): this is just a precautionary measure
      if args.language != 'cs':
          exit("We do not support upload to other languages besides Czech!")

  if args.action in ('upload', 'download', 'update', 'delete'):
      if args.videoids_file:
          exit("Option --videoids-file is incompatible with --action=%s." %
                  args.action)

  youtube = get_authenticated_service(args)

  if args.videoids_file:
    with open(args.videoids_file, 'r') as f:
        youtube_ids = set(f.read().split('\n'))
        youtube_ids.remove('')
  else:
      youtube_ids = set([args.videoid])

  YTID_REGEX = r'^[a-zA-Z0-9_-]{11}$'
  for youtube_id in youtube_ids:
    if not re.fullmatch(YTID_REGEX, youtube_id):
      exit("Invalid YouTube ID: %s" % youtube_id)

  try:
    if args.action == 'upload':
        upload_caption(youtube, ytid, args.language, args.name, args.draft, args.file)
    elif args.action == 'download':
        download_caption(youtube, args.captionid, 'srt')
    elif args.action == 'update':
        update_caption(youtube, ytid, args.language, args.captionid, args.draft, args.file);

    # TODO: This could be optimized, list video API calls can be batched
    # for up to 50 videos
    for ytid in youtube_ids:
        if args.action == 'list':
            list_captions(youtube, ytid)
        elif args.action == 'list_video':
            list_video(youtube, ytid)
        elif args.action == 'video_duration':
            video_duration(youtube, ytid)

  except HttpError as e:
    print("An HTTP error %d occurred:\n%s" % (e.resp.status, e.content))
  else:
    print("Request succesfull!")
