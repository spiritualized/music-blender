import argparse
import os
import textwrap
from colorama import Fore, Back, Style, init as colorama_init
import taglib
import re, math
import bitstring

file_search_limit = 8192

class Mp3Info():
	method = None # CBR/VBR/LAME
	bitrate = None
	xing_vbr_v = None
	xing_vbr_q = None
	lame_version = None
	lame_tag_revision = None
	lame_vbr_method = None
	lame_nspsytune = None
	lame_nssafejoint = None
	lame_nogap_next = None
	lame_nogap_previous = None

	def __init__(self, path):
		stream = bitstring.ConstBitStream(filename=path)

		# look for Xing
		Xing = stream.find("0x58696E67", bytealigned=True)

		if Xing:
			self.method = "VBR"
			stream.bytepos += 4
			xing_flags = stream.read("uint:32")
			if xing_flags & 1:					# skip frames field
				stream.bytepos += 4
			if xing_flags & 2:					# skip bytes field
				stream.bytepos += 4
			if xing_flags & 4:					# skip TOC
				stream.bytepos += 100
			if xing_flags & 8:
				xing_vbr_quality = stream.read("uint:32")
				self.xing_vbr_v = 10 - math.ceil(xing_vbr_quality/10)
				self.xing_vbr_q = 10 - xing_vbr_quality % 10

			# LAME versions < 3.90 do not contain encoder info, and will not be picked up by this. Treat as VBR
			lame_version = stream.read("bytes:9")
			if lame_version[0:4] == b"LAME":
				self.lame_version = lame_version[4:].decode().strip()
				self.lame_tag_revision = stream.read("uint:4")
				self.lame_vbr_method = stream.read("uint:4")
				stream.bytepos += 9
				self.lame_nspsytune = stream.read("bool")
				self.lame_nssafejoint = stream.read("bool")
				self.lame_nogap_next = stream.read("bool")
				self.lame_nogap_previous = stream.read("bool")

				if self.lame_version[-1] == ".":
					self.lame_version = self.lame_version[:-1]

			return

		Info = stream.find("0x496E666F", bytealigned=True)
		if Info:
			self.method = "CBR"
			return

		VBRI = stream.find("0x56425249", bytealigned=True)
		if VBRI:
			self.method = "VBR"
			return

		# Assume CBR...
		self.method = "CBR"

	def __repr__(self):
		return "{0}".format(self.method)


class MusicFile():
	path = None
	metadata = None
	mp3info = None

	def get_filename(self):
		return self.path.split(os.path.sep)[-1]

	def __init__(self, path):
		self.path = path
		self.mp3info =  Mp3Info(path)
		print("Opening {0}".format(path))
		#path2 = path.encode("mbcs")

		self.metadata = taglib.File(path)

	def __repr__(self):
		return self.get_filename()
	def __eq__(self, other):
		return self.get_filename() == other.get_filename()
	def __gt__(self, other):
		return self.get_filename() > other.get_filename()

allowed_extensions = [".mp3", ".flac", ".jpg", ".jpeg", ".log"]

def clean_text(text):
	return re.sub(' +', ' ', text.strip())

def write_tag(track, tag, value):
	track.metadata.tags[tag] = value
	retval = track.metadata.save()
	if len(retval) != 0:
		print("Could not alter track tag: {0}".format(track.metadata))
		exit()

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

# check we have a full set of strictly incrementing tracks, starting at 1
def check_track_numbers(tracks, tag_errors):

	# check track numbers
	track_numbers = []
	for track in tracks:
		if 'TRACKNUMBER' in track.metadata.tags:
			track_num = int(track.metadata.tags['TRACKNUMBER'][0].split("/")[0])
			if track_num > 0:
				track_numbers.append(track_num)
		else:
			curr_num_missing = True
			if fix_track_numbers:
				match = re.search('^(\d{1,2})[ \-_\.]+', track.get_filename())
				if match:
					write_tag(track, 'TRACKNUMBER', [match.group(1)])
					track_numbers.append(int(track.metadata.tags['TRACKNUMBER'][0]))
					curr_num_missing = False

			if curr_num_missing:
				tag_errors.append("{0}: track number missing".format(track.get_filename()))
	
	# check we have a full set of strictly incrementing tracks, starting at 1
	all_tracks_present = len(track_numbers) != 0 and (track_numbers[0] == 1)
	track_numbers = sorted(track_numbers)
	for i in range(0, len(track_numbers)-1):
		if track_numbers[i] != track_numbers[i+1]-1:
			all_tracks_present = False

	if not all_tracks_present:
		flattened_track_nums = ",".join(str(i) for i in track_numbers)
		tag_errors.append("Directory does not have a full set of tracks: {0}".format(flattened_track_nums))


# check the track number-of field
def check_track_number_of(tracks, tag_errors, all_tracks_present):
		
	if not all_tracks_present:
		return

	for track in tracks:
		# skip this check if there are no track numbers at all
		if not 'TRACKNUMBER' in track.metadata.tags:
			continue

		track_num_split = track.metadata.tags['TRACKNUMBER'][0].split("/")
		if len(track_num_split) is 1:
			if all_tracks_present:
				if fix_track_number_of:
					new_tracknumber = str("{0}/{1}".format(track_num_split[0], track_numbers[-1]))
					write_tag(track, 'TRACKNUMBER', [new_tracknumber])
				else:
					tag_errors.append("{0}: track number-of missing, should be {1}".format(track.get_filename(), track_numbers[-1]))
			else:
				tag_errors.append("{0}: track number-of missing".format(track.get_filename()))
			continue
		if int(track_num_split[1]) != track_numbers[-1]:
			tag_errors.append("{0}: track number-of incorrect: {1} should be {2}".format(track.get_filename(), track_num_split[1], track_numbers[-1]))

# check we have a full set of strictly incrementing tracks, starting at 1
def check_disc_numbers(tracks, tag_errors, folder):

	disc_numbers_ok = True
	# check track numbers
	disc_numbers = []
	for track in tracks:
		if 'DISCNUMBER' in track.metadata.tags:
			disc_num = int(track.metadata.tags['DISCNUMBER'][0].split("/")[0])
			if disc_num > 0:
				disc_numbers.append(disc_num)
			else:
				disc_numbers_ok = False
		else:
			disc_numbers_ok = False

	disc_numbers = sorted(set(disc_numbers))
	
	disc_number_candidate = None
	if len(disc_numbers) == 1:
		disc_number_candidate = disc_numbers[0]
	# attempt to extract a disc number from the container
	else:
		match = re.search('(disc|cd)[ ]?(\d{1})', folder.split(os.path.sep)[-1].lower())
		if match:
			disc_number_candidate = match.group(2)
		else:
			disc_number_candidate = "1"


	if not disc_numbers_ok:
		if fix_disc_numbers and disc_number_candidate:
			for track in tracks:
				write_tag(track, 'DISCNUMBER', [str(disc_number_candidate)])
		else:
			if disc_number_candidate:
				tag_errors.append("Directory has missing disc numbers (should be {0})".format(disc_number_candidate))
			else:
				tag_errors.append("Directory has missing disc numbers")

	return disc_numbers

# check the disc number-of field
def check_disc_number_of(tracks, tag_errors, disc_numbers):
		
	for track in tracks:
		# skip this check if there are no track numbers at all
		if not 'DISCNUMBER' in track.metadata.tags:
			continue

		disc_num_split = track.metadata.tags['DISCNUMBER'][0].split("/")
		if len(disc_num_split) is 1:
			if len(disc_numbers) is 1:
				if fix_disc_number_of:
					new_discnumber = str("{0}/{1}".format(disc_num_split[0], disc_numbers[-1]))
					write_tag(track, 'DISCNUMBER', [new_discnumber])
				else:
					tag_errors.append("{0}: disc number-of missing, should be {1}".format(track.get_filename(), disc_numbers[-1]))
			else:
				tag_errors.append("{0}: disc number-of missing".format(track.get_filename()))
			continue


# check all tracks have (correct) titles
def check_track_titles(tracks, tag_errors):
	for track in tracks:
		if not 'TITLE' in track.metadata.tags:
			tag_errors.append("{0}: Track title missing".format(track.get_filename()))
			continue

		if track.metadata.tags['TITLE'][0] != clean_text(track.metadata.tags['TITLE'][0]):
			if clean_text_tags:
				write_tag(track, 'TITLE', [clean_text(track.metadata.tags['TITLE'][0])])
			else:
				tag_errors.append("{0}: Track title has leading/trailing/multiple spaces".format(track.get_filename()))
		if clean_text(track.metadata.tags['TITLE'][0]) == "":
			tag_errors.append("{0}: Track title is missing".format(track.get_filename()))

# check all tracks have (correct) artists
def check_artists(tracks, tag_errors):
	for track in tracks:
		if not 'ARTIST' in track.metadata.tags:
			tag_errors.append("{0}: Track artist missing".format(track.get_filename()))
			continue

		# does anyone use this?
		if len(track.metadata.tags['ARTIST']) > 1:
			print("**ALERT multiple artists in {0}".format(track.get_filename()))
			exit()

		title = clean_text(track.metadata.tags['ARTIST'][0])

		if track.metadata.tags['ARTIST'][0] != clean_text(track.metadata.tags['ARTIST'][0]):
			if clean_text_tags:
				write_tag(track, 'ARTIST', [clean_text(track.metadata.tags['ARTIST'][0])])
			else:
				tag_errors.append("{0}: Track artist has leading/trailing/multiple spaces".format(track.get_filename()))
		if title == "":
			tag_errors.append("{0}: Track artist is missing".format(track.get_filename()))

# check all tracks have (correct) album artist tags
def check_album_artists(tracks, tag_errors):
	album_artist_ok = True
	album_artist_last = None
	artists = []
	for track in tracks:
		if 'ARTIST' in track.metadata.tags:
			artists.append(track.metadata.tags['ARTIST'][0])

		if not 'ALBUMARTIST' in track.metadata.tags:
			album_artist_ok = False
		else:
			if track.metadata.tags['ALBUMARTIST'][0] != clean_text(track.metadata.tags['ALBUMARTIST'][0]):
				if clean_text_tags:
					write_tag(track, 'ALBUMARTIST', [clean_text(track.metadata.tags['ALBUMARTIST'][0])])
				else:
					tag_errors.append("{0}: Album artist has leading/trailing/multiple spaces".format(track.get_filename()))

			if not album_artist_last:
				album_artist_last = track.metadata.tags['ALBUMARTIST'][0]
			else:
				if track.metadata.tags['ALBUMARTIST'][0] != album_artist_last:
					album_artist_ok = False

	if not album_artist_ok:
		# check that we have an artist at all, that all artist tags in album match, and that the match isn't blank
		if fix_album_artist and len(artists) > 0 and artists[1:] == artists[:-1] and clean_text(artists[0]) != "":
			for track in tracks:
				write_tag(track, 'ALBUMARTIST', [clean_text(artists[0])])
		else:
			tag_errors.append("Folder has missing/non-matching album artist tags")

# check all tracks have (correct and matching) year tags
def check_years(tracks, tag_errors, folder):

	# look for a year in the folder name
	year_folder = re.search('[\^\$(\-\[ ](\d{4})[)\^\$\-\] ]', folder.split(os.path.sep)[-1])
	if year_folder:
		year_folder = year_folder.group(1)

	year_ok = True
	year_last = None	
	year_any = None

	# find *any* track containing a year
	for track in tracks:
		if 'DATE' in track.metadata.tags:
			year_any = track.metadata.tags['DATE'][0].split("-")[0]


	for track in tracks:
		if not 'DATE' in track.metadata.tags:
			year_ok = False
		else:
			if not year_last:
				year_last = track.metadata.tags['DATE'][0].split("-")[0]
			else:
				if track.metadata.tags['DATE'][0].split("-")[0] != year_last:
					year_ok = False



	if not year_ok:
		# if we are in fix-mode, re-iterate and apply the year to all tracks
		if fix_year and (year_any or year_folder):
			for track in tracks:
				if year_any:
					write_tag(track, 'DATE', [year_any])
				if year_folder:
					write_tag(track, 'DATE', [year_folder])
		else:
			tag_errors.append("Folder has missing/non-matching year tags")

# check all tracks have (correct and matching) album titles
def check_album_titles(tracks, tag_errors):
	album_ok = True
	album_last = None
	for track in tracks:
		if not 'ALBUM' in track.metadata.tags:
			album_ok = False
		else:
			if track.metadata.tags['ALBUM'][0] != clean_text(track.metadata.tags['ALBUM'][0]):
				tag_errors.append("{0}: Album title has leading/trailing/multiple spaces".format(track.get_filename()))

			if not album_last:
				album_last = track.metadata.tags['ALBUM'][0]
			else:
				if track.metadata.tags['ALBUM'][0] != album_last:
					album_ok = False

	if not album_ok:
		tag_errors.append("Folder has missing/non-matching album titles")

# check filenames
def check_filenames(tracks, tag_errors, folder):
	for track in tracks:
		if 'TRACKNUMBER' not in track.metadata.tags or 'TITLE' not in track.metadata.tags or 'ARTIST' not in track.metadata.tags:
			tag_errors.append("Impossible to validate filename {0}".format(track.get_filename()))

		correct_filename = "{0} - {1}.mp3".format(track.metadata.tags['TRACKNUMBER'][0].split("/")[0].zfill(2), clean_text(track.metadata.tags['TITLE'][0]))
		if os.name == "nt":
			correct_filename = correct_filename.replace("?", "_")
		if track.get_filename() != correct_filename:
			if fix_filenames:
				track.metadata.close()
				tracks.remove(track)
				os.rename(track.path, os.path.join(os.path.dirname(track.path), correct_filename))
				track = MusicFile(os.path.join(folder, correct_filename))
				tracks.append(track)
			else:
				tag_errors.append("Invalid filename {0}, should be {1}".format(track.get_filename(), correct_filename))
	return sorted(tracks)

def check_bitrates(tracks, tag_errors):

	overall_bitrate = None
	vbr_accumulator = 0

	for track in tracks:
		curr_track_bitrate = None

		if track.mp3info.lame_version:
			if track.mp3info.lame_vbr_method == 3:
				if track.mp3info.xing_vbr_v == 2:
					curr_track_bitrate = "APS"
				else:
					raise ValueError("I don't know what kind of --vbr-old this is")
			elif track.mp3info.lame_vbr_method in [4,5]:
				curr_track_bitrate = "V{0}".format(track.mp3info.xing_vbr_v)
			else:
				raise ValueError("I don't know what kind of lame_vbr_method this is ({0})".format(track.mp3info.lame_vbr_method))
		#print("method {0}, vbr-v {1}, vbr-q {2}".format(track.mp3info.lame_vbr_method, track.mp3info.xing_vbr_v, track.mp3info.xing_vbr_q))

		elif track.mp3info.method == "CBR":
			curr_track_bitrate = "CBR{0}".format(track.metadata.bitrate)

		elif track.mp3info.method == "VBR":
			curr_track_bitrate = "VBR"
			vbr_accumulator += track.metadata.bitrate


		if overall_bitrate is None:
			overall_bitrate = curr_track_bitrate
		elif overall_bitrate != curr_track_bitrate:
			return "~"

	if overall_bitrate == "VBR":
		overall_bitrate = "VBR{0}".format(int(vbr_accumulator/len(tracks)))

	return overall_bitrate



def check_folder_name(tracks, tag_errors, folder, bitrate):

	if not len(tag_errors) == 0:
		tag_errors.append("Folder name validation impossible")
		return

	current_folder_name = folder.split(os.path.sep)[-1]
	current_folder_parent = os.path.dirname(folder)

	album_artist = tracks[0].metadata.tags['ALBUMARTIST'][0]
	year = tracks[0].metadata.tags['DATE'][0].split("-")[0]
	album = tracks[0].metadata.tags['ALBUM'][0]
	correct_folder_name = "{0} - {1} - {2} [{3}]".format(album_artist, year, album, bitrate)
	
	if current_folder_name != correct_folder_name:
		if fix_foldernames:
			for track in tracks:
				track.metadata.close()

			if not os.path.exists(os.path.join(current_folder_parent, correct_folder_name)):
				os.rename(os.path.join(current_folder_parent, current_folder_name), os.path.join(current_folder_parent, correct_folder_name))
			else:
				tag_errors.append("Destination folder {0} already exists".format(os.path.join(current_folder_parent, correct_folder_name)))

		else:
			tag_errors.append("Folder name should be {0}, not {1}".format(correct_folder_name, current_folder_name))



def check_tags(folder, subfolder_mode=False):
	items = os.listdir(folder)

	tag_errors = []

	tracks = []

	for i in items:
		if os.path.isdir(os.path.join(folder, i)):
			continue

		if os.path.splitext(i)[-1].lower() == ".mp3":
			tmp = os.path.join(folder, i)
			tracks.append(MusicFile(os.path.join(folder, i)))
			
	check_album_titles(tracks, tag_errors)
	check_track_titles(tracks, tag_errors)
	check_artists(tracks, tag_errors)
	check_album_artists(tracks, tag_errors)
	check_years(tracks, tag_errors, folder)

	all_tracks_present = check_track_numbers(tracks, tag_errors)
	check_track_number_of(tracks, tag_errors, all_tracks_present)

	disc_numbers = check_disc_numbers(tracks, tag_errors, folder)

	if not subfolder_mode:
		check_disc_number_of(tracks, tag_errors, disc_numbers)

	tracks = check_filenames(tracks, tag_errors, folder)
	bitrate = check_bitrates(tracks, tag_errors)
	
	# must be done last
	check_folder_name(tracks, tag_errors, folder, bitrate)

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

try:
	print(u"\u2603 Scraper running...")
except:
	print("""Unicode error - run the program again.""")
	os.system("chcp 65001")
	exit()
	
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
parser.add_argument('--fix-track-numbers', action='store_true',
                   help='Attempt to fix missing track numbers')
parser.add_argument('--fix-track-number-of', action='store_true',
                   help='Attempt to fix missing track number of tags')
parser.add_argument('--fix-disc-numbers', action='store_true',
                   help='Attempt to fix missing disc numbers')
parser.add_argument('--fix-disc-number-of', action='store_true',
                   help='Attempt to fix missing disc number-of tags')
parser.add_argument('--fix-album-artist', action='store_true',
                   help='Attempt to fix missing album artist tags')
parser.add_argument('--fix-year', action='store_true',
                   help='Attempt to fix missing year tags')
parser.add_argument('--clean-text-tags', action='store_true',
                   help='Clean up leading/trailing/multiple whitespace')
parser.add_argument('--fix-filenames', action='store_true',
                   help='Validate filenames')
parser.add_argument('--fix-foldernames', action='store_true',
                   help='Validate folder names')




args = parser.parse_args()

source = args.source
destination = args.dest
operation_mode = args.mode
delete_disallowed_files = args.delete_disallowed_files
fix_track_numbers = args.fix_track_numbers
fix_track_number_of = args.fix_track_number_of
fix_album_artist = args.fix_album_artist
fix_year = args.fix_year
fix_disc_numbers = args.fix_disc_numbers
fix_disc_number_of = args.fix_disc_number_of
clean_text_tags = args.clean_text_tags
fix_filenames = args.fix_filenames
fix_foldernames = args.fix_foldernames

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

total_failure_reasons = 0

for curr in folders:

	full_path = os.path.join(source, curr)

	if not os.path.isdir(full_path):
		print("{0} {1}".format(string_colour("[FAIL]", Fore.RED), curr))
		continue

	failure_reasons = validate_folder(full_path)
	total_failure_reasons += len(failure_reasons)

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

print("Total tag errors: {0}".format(total_failure_reasons))


# subfolder CD1/2
# implement musicCRC?