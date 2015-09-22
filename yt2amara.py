#!/usr/bin/env python
from subprocess import Popen, PIPE, call, check_call
import argparse, sys
from pprint import pprint
from amara_api import *

def read_cmd():
   """Function for reading command line options."""
   desc = "Program for copying subtitles from YouTube to Amara."
   parser = argparse.ArgumentParser(description=desc)
   parser.add_argument('input_file',metavar='INPUT_FILE', help='Text file containing a column of YouTube IDs.')
   parser.add_argument('-c','--credentials',dest='apifile',default='myAPI.txt', help='Text file containing your API key and username on the first line.')
   return parser.parse_args()

opts = read_cmd()
infile = opts.input_file
apifile = opts.apifile

# File 'apifile' should contain only one line with your Amara API key and Amara username.
# Amara API can be found in Settins->Account-> API Access (bottom-right corner)
file = open(apifile, "r")
API_KEY, USERNAME = file.read().split()[0:]
print('Using Amara username: '+USERNAME)
print('Using Amara API key: '+API_KEY)

ytids = []
with open(infile, "r") as f:
   for line in f:
       ytids.append(line.replace('\n', ''))

amara_headers = {
   'Content-Type': 'application/json',
   'X-api-username': USERNAME,
   'X-api-key': API_KEY,
   'format': 'json'
}

lang = 'en'
is_original = True # is lang the original language of the video?
is_complete = True # do we upload complete subtitles?
sub_format = 'srt'

for ytid in ytids:
    ytdownload='youtube-dl --sub-lang "en" --sub-format "srt" --write-sub --skip-download '+ ytid
    
    p = Popen(ytdownload, shell=True, stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()
    f = open("youtubedl.out", "a")
    f.write(out)
    f.close()
    if err:
        print(err)
        print("Error during downloading subtitles..")
        sys.exit(1)
    fname = out.split('Writing video subtitles to: ')[1].strip('\n')
    print('Subtitles downloaded to file:'+fname)
    with open(fname, 'r') as content_file:
            subs = content_file.read()
    
    # Now check whether the video is already on Amara
    # If not, create it.
    video_url = 'https://www.youtube.com/watch?v='+ytid
    amara_response = check_video( video_url, amara_headers)
    if amara_response['meta']['total_count'] == 0:
        amara_response = add_video(video_url, lang, amara_headers)
        amara_id = amara_response['id']
        amara_title =  amara_response['title']
        print("Created video on Amara with Amara id "+amara_id)
        print("Title: "+amara_title)
        print(AMARA_BASE_URL+'cs/videos/'+amara_id)
    else:
        amara_id =  amara_response['objects'][0]['id']
        amara_title =  amara_response['objects'][0]['title']
        print("Video with YTid "+ytid+" is already present on Amara")
        print("Title: "+amara_title)
        print(AMARA_BASE_URL+'cs/videos/'+amara_id)


    # First check, whether subtitles for a given language are present,
    # then upload subtitles
    is_present, sub_version = check_language(amara_id, lang, amara_headers)
    if is_present:
        print("Language "+lang+" is already present in Amara video id:"+amara_id)
        print("Subtitle revision number: "+str(sub_version))
        print("Should I upload the subtitles anyway? [yes/no]")
        answer = ''
        while answer != "no" and answer != "yes":
            answer = raw_input('-->')
            if answer == "yes":
                r = upload_subs(amara_id, lang, is_complete, subs, sub_format, amara_headers)
                if r['version_no'] == sub_version+1:
                    print('Succesfully uploaded subtitles to: '+r['site_uri'])
            elif answer == "no":
                pass
            else:
                print("Please enter yes or no.")
    else:
        r = add_language(amara_id, lang, is_original, amara_headers)
        r = upload_subs(amara_id, lang, is_complete, subs, sub_format, amara_headers)
        if r['version_no'] == sub_version+1:
            print('Succesfully uploaded subtitles to: '+r['site_uri'])
        else:
            print("This is weird. Something probably went wrong during upload.")
            print("This is the response I got from Amara")
            pprint(r)
            sys.exit(1)

    print('----------------------------------------')


