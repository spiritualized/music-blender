import argparse
import os
import textwrap
from colorama import Fore, Back, Style, init as colorama_init
import taglib
import re

allowed_extensions = [".mp3", ".flac", ".jpg", ".jpeg", ".log"]

# return true if folder contains any subfolders
def check_subfolders(folder):
	items = os.listdir(folder)

	for i in items:
		if os.path.isdir(os.path.join(folder, i)):
			return True
	return False

def check_disallowed_files(folder):
	items = os.listdir(folder)

	disallowed_files = []

	for i in items:

		# skip folders
		if os.path.isdir(os.path.join(folder, i)):
			continue

		ext = os.path.splitext(i)[-1].lower()
		if ext not in allowed_extensions:

			# delete the file if appropriate
			if delete_disallowed_files:
				os.remove(os.path.join(folder, i))
			# otherwise, add to failure reasons
			else:
				disallowed_files.append(i)
	return disallowed_files

def check_tags(folder):
	items = os.listdir(folder)

	tag_errors = []

	tracks = {}

	for i in items:
		if os.path.isdir(os.path.join(folder, i)):
			continue

		if os.path.splitext(i)[-1].lower() == ".mp3":
			tracks[i] = taglib.File(os.path.join(folder, i))
	
	# check track numbers
	track_numbers = []
	for filename, track in sorted(tracks.items()):
		if track.tags['TRACKNUMBER']:
			track_num = int(track.tags['TRACKNUMBER'][0].split("/")[0])
			if track_num > 0:
				track_numbers.append(track_num)
		else:
			tag_errors.append("{0}: track number missing".format(filename))
	
	# check we have a full set of strictly incrementing tracks, starting at 1
	all_tracks_present = (track_numbers[0] == 1)
	for i in range(0, len(track_numbers)-1):
		if track_numbers[i] != track_numbers[i+1]-1:
			all_tracks_present = False

	if not all_tracks_present:
		flattened_track_nums = ",".join(str(i) for i in track_numbers)
		tag_errors.append("Directory does not have a full set of tracks: {0}".format(flattened_track_nums))

	for filename, track in sorted(tracks.items()):
		track_num_split = track.tags['TRACKNUMBER'][0].split("/")
		if len(track_num_split) is 1:
			tag_errors.append("{0}: track number-of missing".format(filename))
			continue
		if int(track_num_split[1]) != track_numbers[-1]:
			tag_errors.append("{0}: track number-of incorrect: {1} should be {2}".format(filename, track_num_split[1], track_numbers[-1]))

	# check all tracks have (correct) titles
	for filename, track in sorted(tracks.items()):
		if not 'TITLE' in track.tags:
			tag_errors.append("{0}: Track title missing".format(filename))
			continue

		title = re.sub(' +', ' ', track.tags['TITLE'][0].strip())

		if title != track.tags['TITLE'][0]:
			tag_errors.append("{0}: Track title has leading/trailing/multiple spaces".format(filename))
		if title == "":
			tag_errors.append("{0}: Track title is missing".format(filename))

	# check all tracks have (correct) artists
	for filename, track in sorted(tracks.items()):
		if not 'ARTIST' in track.tags:
			tag_errors.append("{0}: Track artist missing".format(filename))
			continue

		# does anyone use this?
		if len(track.tags['ARTIST']) > 1:
			print("**ALERT multiple artists in {0}".format(filename))
			exit()

		title = re.sub(' +', ' ', track.tags['ARTIST'][0].strip())

		if title != track.tags['ARTIST'][0]:
			tag_errors.append("{0}: Track artist has leading/trailing/multiple spaces".format(filename))
		if title == "":
			tag_errors.append("{0}: Track artist is missing".format(filename))



	return tag_errors

def validate_folder(folder):

	failure_reasons = []

	if check_subfolders(folder):
		failure_reasons.append("Subfolder present")

	disallowed_files = check_disallowed_files(folder)
	for file in disallowed_files:
		failure_reasons.append("Disallowed file: {0}".format(file))

	tag_errors = check_tags(folder)
	for error in tag_errors:
		failure_reasons.append("Tag error: {0}".format(error))

	return failure_reasons

def string_colour(string, color):
	return "".join([color, string, Style.RESET_ALL])
def string_background(string, color):
	return "".join([color, string, Style.RESET_ALL])

#colorama
colorama_init(autoreset=True)

#argparse
parser = argparse.ArgumentParser(description='Validate a music collection.', prefix_chars='--',
				formatter_class=argparse.RawDescriptionHelpFormatter,  epilog='''\
Operation modes:
  	move - moves validated folders to destination folder
  	copy - leaves original files intact, creates validated copies in destination folder
  	inplace - applies fixes to the files and leaves them in the source folder'''
            )
parser.add_argument('mode', metavar='mode', type=str, choices=['move', 'copy', 'inplace'],
                   help='Operation mode',
                   )

parser.add_argument('source', metavar='directory', type=str,
                   help='Top level folder containing all albums')
parser.add_argument('--dest', metavar='destination', type=str,
                   help='Leave original files untouched, create fixed versions in this directory')
parser.add_argument('--delete-disallowed-files', action='store_true',
                   help='Delete superfluous files in album base directories')



args = parser.parse_args()

source = args.source
destination = args.dest
operation_mode = args.mode
delete_disallowed_files = args.delete_disallowed_files

if not os.path.isdir(source):
	print("Source folder {0} does not exist".format(source))
	exit()

if operation_mode is "copy" or operation_mode is "move":
	if not os.path.isdir(destination):
		print("Destination folder {0} does not exist".format(destination))
		exit()

folders = os.listdir(source)
print("Scanning {0} subfolders...".format(len(folders)))

last_failed = False

for curr in folders:

	full_path = os.path.join(source, curr)

	if not os.path.isdir(full_path):
		print("{0} {1}".format(string_colour("[FAIL]", Fore.RED), curr))
		continue

	failure_reasons = validate_folder(full_path)

	if len(failure_reasons) is not 0:

		if last_failed is False:
			print("-----------------------------------")
		print("{0} {1}".format(string_colour("[FAIL]", Fore.RED), curr))

		for reason in failure_reasons:
			print(string_background(reason, Back.RED))
		print("-----------------------------------")

		last_failed = True


	else:

		print("{0} {1}".format(string_colour("[PASS]", Fore.GREEN), curr))
		last_failed = False


# subfolders
# banned extensions
# mime check
# title, artist, album, album_artist, tracknum, tracknum_of, discnum, discnum_of
# encoding
# folder