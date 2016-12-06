import os
import re, math
import bitstring

import taglib
import musicbrainzngs
import json

class blender():

	# checks
	delete_disallowed_files = False
	fix_track_numbers = False
	fix_track_number_of = False
	fix_album_artist = False
	fix_year = False
	fix_disc_numbers = False
	fix_disc_number_of = False
	fix_filenames = False
	fix_foldernames = False

	# folders
	current_folder = None
	move_to = None
	tracks = None
	tag_errors = None

	years_ok = False
	subfolders_ok = False
	disallowed_files_ok = False
	track_numbers_ok = False
	track_number_of_ok = False
	disc_numbers_ok = False
	disc_number_of_ok = False
	track_titles_ok = False
	artists_ok = False
	album_artist_ok = False
	album_title_ok = False
	filenames_ok = False
	musicbrainz_ok = False


	def __init__(self):
		musicbrainzngs.set_useragent("music-blender", "0.1", "")


	def set_move_to(self, path):
		if not os.path.isdir(path):
			print("Move-to destination folder {0} does not exist".format(path))
			return
		self.move_to = path

	def open_folder(self, path):

		self.years_ok = False
		self.subfolders_ok = False
		self.disallowed_files_ok = False
		self.track_numbers_ok = False
		self.track_number_of_ok = False
		self.disc_numbers_ok = False
		self.disc_number_of_ok = False
		self.track_titles_ok = False
		self.artists_ok = False
		self.album_artist_ok = False
		self.album_title_ok = False
		self.filenames_ok = False
		self.musicbrainz_ok = False

		if not os.path.isdir(path):
			print("Folder {0} does not exist".format(source))
			return
		self.current_folder = path

		self.tracks = []
		self.tag_errors = []
		items = os.listdir(self.current_folder)

		for i in items:
			if os.path.isdir(os.path.join(self.current_folder, i)):
				continue

			if os.path.splitext(i)[-1].lower() == ".mp3":
				path = os.path.join(self.current_folder, i)

				# check for empty files
				if not os.path.getsize(path):
					continue
				
				self.tracks.append(MusicFile(path))


	def validate_folder(self):

		if len(self.tracks) == 0:
			self.tag_errors.append("Folder contains no tracks")

		self.check_subfolders()
		if not self.subfolders_ok:
			self.tag_errors.append("Subfolder present")

		disallowed_files = self.check_disallowed_files()
		for file in disallowed_files:
			self.tag_errors.append("Disallowed file: {0}".format(file))

		self.check_tags()

		return self.tag_errors

	def check_tags(self, subfolder_mode=False):

		if not len(self.tracks):
			return

		# disc numbers before track numbers
		disc_numbers = self.check_disc_numbers()

		if not subfolder_mode:
			self.check_disc_number_of(disc_numbers)
				
		self.check_album_titles()
		self.check_track_titles()
		self.check_artists()
		self.check_album_artists()
		self.check_years()
		self.musicbrainz_verify()

		all_tracks_present = self.check_track_numbers()
		self.check_track_number_of(all_tracks_present)



		self.check_filenames()
		bitrate = self.get_overall_bitrate()
		

		if self.album_artist_ok == False or self.artists_ok == False or self.album_title_ok == False:
			self.tag_errors.append("Folder name validation impossible")
			return self.tag_errors

		# must be done last
		correct_folder_name = self.get_correct_folder_name(bitrate)

		# update the current folder name
		self.current_folder = os.path.join(os.path.dirname(self.current_folder), correct_folder_name)

		# move to the output folder if required
		if len(self.tag_errors) == 0 and self.move_to and not os.path.exists(os.path.join(self.move_to, correct_folder_name)):

			for track in self.tracks:
					track.close()
			os.rename(self.current_folder, os.path.join(self.move_to, correct_folder_name))

		return self.tag_errors

	# check all tracks have (correct and matching) year tags
	def check_years(self):

		# look for a year in the folder name
		year_folder = re.search('[\^\$(\-\[ ](\d{4})[)\^\$\-\] ]', self.current_folder.split(os.path.sep)[-1])
		if year_folder:
			year_folder = year_folder.group(1)

		self.year_ok = True
		year_last = None	
		year_any = None

		# find *any* track containing a year
		for track in self.tracks:
			if track.get_tag('DATE'):
				year_any = track.get_tag('DATE').split("-")[0]

		for track in self.tracks:
			if not  track.get_tag('DATE'):
				self.year_ok = False
			else:
				if not year_last:
					year_last = track.get_tag('DATE').split("-")[0]
				else:
					if track.get_tag('DATE').split("-")[0] != year_last:
						self.year_ok = False



		if not self.year_ok:
			# if we are in fix-mode, re-iterate and apply the year to afll tracks
			if self.fix_year and (year_any or year_folder):
				for track in self.tracks:
					if year_any:
						track.write_tag('DATE', [year_any])
					if year_folder:
						track.write_tag('DATE', [year_folder])
			else:
				self.tag_errors.append("Folder has missing/non-matching year tags")


	# check if there are any (unwanted) subfolders
	def check_subfolders(self):
		items = os.listdir(self.current_folder)

		for i in items:
			if os.path.isdir(os.path.join(self.current_folder, i)):
				self.subfolders_ok = False
				return
		self.subfolders_ok = True

	# check for non-whitelisted file types
	def check_disallowed_files(self):
		items = os.listdir(self.current_folder)

		disallowed_files = []

		for i in items:

			# skip folders
			if os.path.isdir(os.path.join(self.current_folder, i)):
				continue
			if i == ".mix":
				continue
			ext = os.path.splitext(i)[-1].lower()
			if ext not in allowed_extensions:

				# delete the file if appropriate
				if self.delete_disallowed_files:
					os.remove(os.path.join(self.current_folder, i))
				# otherwise, add to failure reasons
				else:
					disallowed_files.append(i)

		if len(disallowed_files) == 0:
			self.disallowed_files_ok = True

		return disallowed_files

	# check the folder havs a full set of strictly incrementing tracks, starting at 1
	def check_track_numbers(self):

		# check track numbers
		track_numbers = {}
		for track in self.tracks:
			track_num = None

			disc_num = int(track.get_tag('DISCNUMBER').split("/")[0]) or 1
			if not track_numbers.get(disc_num):
					track_numbers[disc_num] = []

			if track.get_tag('TRACKNUMBER'):
				try:
					track_num = int(track.get_tag('TRACKNUMBER').split("/")[0])

					if track_num > 0:
						track_numbers[disc_num].append(track_num)
				except ValueError:
					self.tag_errors.append("Invalid track number, examine manually: {0}".format(track.get_filename()))
			if not track_num:
				curr_num_missing = True
				if self.fix_track_numbers:
					match = re.search('(\d{1,2})[ \-_\.]+', track.get_filename())
					if match:
						track.write_tag('TRACKNUMBER', [match.group(1)])
						track_numbers[disc_num].append(int(track.get_tag('TRACKNUMBER')))
						curr_num_missing = False

				if curr_num_missing:
					self.tag_errors.append("{0}: track number missing".format(track.get_filename()))


		# check we have a full set of strictly incrementing tracks, starting at 1
		all_tracks_present = len(track_numbers) != 0
		
		for disc in track_numbers:
			if len(track_numbers[disc]) == 0:
				all_tracks_present = False
				break

			if track_numbers[disc][0] != 1:
				all_tracks_present = False

			curr_track_numbers = sorted(track_numbers[disc])
			for i in range(0, len(curr_track_numbers)-1):
				if curr_track_numbers[i] != curr_track_numbers[i+1]-1:
					all_tracks_present = False

		if not all_tracks_present:
			flattened_track_nums = ""
			for disc in track_numbers:
				flattened_track_nums += " Disc " + str(disc) + ": " + ",".join(str(i) for i in track_numbers[disc])
			self.tag_errors.append("Directory does not have a full set of tracks:{0}".format(flattened_track_nums))


		self.track_numbers_ok = all_tracks_present

	# check the track number-of field
	def check_track_number_of(self, all_tracks_present):
			
		if not all_tracks_present:
			return

		self.track_number_of_ok = True

		for track in self.tracks:
			# skip this check if there are no track numbers at all
			if not track.get_tag('TRACKNUMBER'):
				continue

			track_num_split = track.get_tag('TRACKNUMBER').split("/")
			if len(track_num_split) is 1:
				if all_tracks_present:
					if self.fix_track_number_of:
						new_tracknumber = str("{0}/{1}".format(track_num_split[0], track_numbers[-1]))
						track.write_tag('TRACKNUMBER', [new_tracknumber])
					else:
						self.tag_errors.append("{0}: track number-of missing, should be {1}".format(track.get_filename(), track_numbers[-1]))
						self.track_number_of_ok = False
				else:
					self.tag_errors.append("{0}: track number-of missing".format(track.get_filename()))
					self.track_number_of_ok = False
				continue
			if int(track_num_split[1]) != track_numbers[-1]:
				self.tag_errors.append("{0}: track number-of incorrect: {1} should be {2}".format(track.get_filename(), track_num_split[1], track_numbers[-1]))
				self.track_number_of_ok = False

	# check we have a full set of strictly incrementing tracks, starting at 1
	def check_disc_numbers(self):

		self.disc_numbers_ok = True
		# check track numbers
		disc_numbers = []
		for track in self.tracks:
			if track.get_tag('DISCNUMBER'):
				disc_num = int(track.get_tag('DISCNUMBER').split("/")[0])
				if disc_num > 0:
					disc_numbers.append(disc_num)
				else:
					self.disc_numbers_ok = False
			else:
				self.disc_numbers_ok = False

		disc_numbers = sorted(set(disc_numbers))
		
		disc_number_candidate = None
		if len(disc_numbers) == 1:
			disc_number_candidate = disc_numbers[0]
		# attempt to extract a disc number from the container
		else:
			match = re.search('(disc|cd)[ ]?(\d{1})', self.current_folder.split(os.path.sep)[-1].lower())
			if match:
				disc_number_candidate = match.group(2)
			else:
				disc_number_candidate = "1"


		if not self.disc_numbers_ok:
			if self.fix_disc_numbers and disc_number_candidate:
				for track in self.tracks:
					track.write_tag('DISCNUMBER', [str(disc_number_candidate)])

				# for use by disc_number_of
				disc_numbers.append(disc_number_candidate)
			else:
				if disc_number_candidate:
					self.tag_errors.append("Directory has missing disc numbers (should be {0})".format(disc_number_candidate))
				else:
					self.tag_errors.append("Directory has missing disc numbers")

		return disc_numbers

	# check the disc number-of field
	def check_disc_number_of(self, disc_numbers):

		self.disc_number_of_ok = True

		for track in self.tracks:
			# skip this check if there are no track numbers at all
			if not track.get_tag('DISCNUMBER'):
				continue

			disc_num_split = track.get_tag('DISCNUMBER').split("/")
			if len(disc_num_split) is 1:
				if len(disc_numbers) != 0:
					if self.fix_disc_number_of:
						new_discnumber = str("{0}/{1}".format(disc_num_split[0], disc_numbers[-1]))
						track.write_tag('DISCNUMBER', [new_discnumber])
					else:
						self.tag_errors.append("{0}: disc number-of missing, should be {1}".format(track.get_filename(), disc_numbers[-1]))
						self.disc_number_of_ok = True
				else:
					self.tag_errors.append("{0}: disc number-of missing".format(track.get_filename()))
					self.disc_number_of_ok = True
				continue

	# check all tracks have (correct) titles
	def check_track_titles(self):

		self.track_titles_ok = True

		for track in self.tracks:
			if not track.get_tag('TITLE'):
				self.tag_errors.append("{0}: Track title missing".format(track.get_filename()))
				self.track_titles_ok = False
				continue

			if track.get_tag('TITLE') == "":
				self.tag_errors.append("{0}: Track title is missing".format(track.get_filename()))
				self.track_titles_ok = False

	# check all tracks have (correct) artists
	def check_artists(self):

		self.artists_ok = True

		for track in self.tracks:
			if not track.get_tag('ARTIST') or track.get_tag('ARTIST') == "":
				self.tag_errors.append("{0}: Track artist missing".format(track.get_filename()))
				self.artists_ok = False
				continue

	# check all tracks have (correct) album artist tags
	def check_album_artists(self):
		self.album_artist_ok = True
		album_artist_last = None
		artists = []
		for track in self.tracks:
			if track.get_tag('ARTIST', True):
				artists.append(track.get_tag('ARTIST', True))

			if not track.get_tag('ALBUMARTIST', True):
				self.album_artist_ok = False
			else:
				if not album_artist_last:
					album_artist_last = track.get_tag('ALBUMARTIST', True)
				else:
					if track.get_tag('ALBUMARTIST', True) != album_artist_last:
						self.album_artist_ok = False

		if not self.album_artist_ok:
			# check that we have an artist at all, that all artist tags in album match, and that the match isn't blank
			if self.fix_album_artist and len(artists) > 0 and artists[1:] == artists[:-1] and artists[0][0] != "":
				for track in self.tracks:
					track.write_tag('ALBUMARTIST', artists[0])
			else:
				self.tag_errors.append("Folder has missing/non-matching album artist tags")

	# check all tracks have (correct and matching) album titles
	def check_album_titles(self):
		self.album_title_ok = True
		album_last = None
		for track in self.tracks:
			if not track.get_tag('ALBUM'):
				self.album_title_ok = False
			else:
				if not album_last:
					album_last = track.get_tag('ALBUM')
				else:
					if track.get_tag('ALBUM') != album_last:
						self.album_title_ok = False

		if not self.album_title_ok:
			self.tag_errors.append("Folder has missing/non-matching album titles")

	# check filenames
	def check_filenames(self):

		self.filenames_ok = True

		out_tracks = []

		for track in self.tracks:
			if not track.get_tag('TRACKNUMBER') or not track.get_tag('TITLE') or not track.get_tag('ARTIST'):
				self.tag_errors.append("Impossible to validate filename {0}".format(track.get_filename()))
				self.filenames_ok = False
				self.tracks = sorted(self.tracks)
				return

			# if a multi disc album, prepend the disc number to the track number in the filename
			if track.get_tag('DISCNUMBER') and track.get_tag('DISCNUMBER').split("/")[1] != "1":
				disc_num = track.get_tag('DISCNUMBER').split("/")[0]
			else:
				disc_num = ""


			correct_filename = "{0}{1} - {2}.mp3".format(disc_num, track.get_tag('TRACKNUMBER').split("/")[0].zfill(2), track.get_tag('TITLE'))
			correct_filename = nt_path_fix(correct_filename)

			new_track = track
			
			if track.get_filename() != correct_filename:
				if self.fix_filenames:
					track.close()
					try:
						new_path = os.path.join(os.path.dirname(track.path), correct_filename)
						if os.name == "nt" and len(new_path) > 260:
							fn, ext = os.path.splitext(new_path)
							new_path = new_path[0:259-len(ext)] + ext

						os.rename(track.path, new_path)
						new_track = MusicFile(new_path)
					except FileExistsError:
						self.tag_errors.append("Duplicate filename: {0}".format(correct_filename))
						self.filenames_ok = False
						continue
				else:
					self.tag_errors.append("Invalid filename {0}, should be {1}".format(track.get_filename(), correct_filename))
					self.filenames_ok = False

			out_tracks.append(new_track)

		self.tracks = out_tracks

	def get_overall_bitrate(self):

		overall_bitrate = None
		vbr_accumulator = 0

		for track in self.tracks:
			curr_track_bitrate = None

			if track.mp3info.lame_version:

				if track.mp3info.lame_vbr_method in [1,8]:
					curr_track_bitrate = "CBR{0}".format(track.bitrate)

				elif track.mp3info.lame_vbr_method == 3:
					if track.mp3info.xing_vbr_v == 0:
						curr_track_bitrate = "APE"
					elif track.mp3info.xing_vbr_v == 1:
						curr_track_bitrate = "APM"
					elif track.mp3info.xing_vbr_v == 2:
						curr_track_bitrate = "APS"
					else:
						curr_track_bitrate = "vbr-old V{0}".format(track.mp3info.xing_vbr_v)
						#raise ValueError("I don't know what kind of --vbr-old this is ({0})".format(track.mp3info.xing_vbr_v))

				elif track.mp3info.lame_vbr_method in [4,5]:
					curr_track_bitrate = "V{0}".format(track.mp3info.xing_vbr_v)
				elif track.mp3info.lame_vbr_method in [2,9]:
					curr_track_bitrate = "ABR"
					vbr_accumulator += track.bitrate
				else:
					curr_track_bitrate = "lame_vbr_method {0}".format(track.mp3info.lame_vbr_method)
					#raise ValueError("I don't know what kind of lame_vbr_method this is ({0})".format(track.mp3info.lame_vbr_method))
			
			elif track.mp3info.method == "CBR":
				curr_track_bitrate = "CBR{0}".format(track.bitrate)

			elif track.mp3info.method == "VBR":
				curr_track_bitrate = "VBR"
				vbr_accumulator += track.bitrate


			if overall_bitrate is None:
				overall_bitrate = curr_track_bitrate
			elif overall_bitrate != curr_track_bitrate:
				return "mixed"

		if overall_bitrate in ["VBR", "ABR"]:
			overall_bitrate = "VBR{0}".format(int(vbr_accumulator/len(self.tracks)))

		return overall_bitrate

	def get_correct_folder_name(self, bitrate):

		current_folder_name = self.current_folder.split(os.path.sep)[-1]
		current_folder_parent = os.path.dirname(self.current_folder)

		album_artist = self.tracks[0].get_flattened('ALBUMARTIST')
		album = self.tracks[0].get_tag('ALBUM')
		year_segment = ""
		if self.year_ok:
			year_segment = " - {0}".format(self.tracks[0].metadata.tags['DATE'][0].split("-")[0])

		artists = []
		for track in self.tracks:
			artists.append(track.get_tag('ARTIST'))
		artists = list(set(artists))
		#print(artists)

		# VA album
		if len(artists) > 4 or os.path.exists(os.path.join(self.current_folder, ".mix")):
			correct_folder_name = "VA - {0}{1} - {2} [{3}]".format(album, year_segment, album_artist, bitrate)

		# standard naming
		else:
			correct_folder_name = "{0}{1} - {2} [{3}]".format(album_artist, year_segment, album, bitrate)
		
		correct_folder_name = nt_path_fix(correct_folder_name)
		
		if current_folder_name != correct_folder_name:
			if self.fix_foldernames:
				for track in self.tracks:
					track.close()

				path_curr = os.path.join(current_folder_parent, current_folder_name)
				path_correct = os.path.join(current_folder_parent, correct_folder_name)

				# if the path doesn't exist, or we are renaming in a case-insensitive OS
				if not os.path.exists(path_correct) or path_curr.lower() == path_correct.lower():
					os.rename(path_curr, path_correct)
				else:
					self.tag_errors.append("Destination folder {0} already exists".format(path_correct))

			else:
				self.tag_errors.append("Folder name should be {0}, not {1}".format(correct_folder_name, current_folder_name))

		return correct_folder_name

	def musicbrainz_verify(self):
		return
		if not self.album_artist_ok or not self.album_title_ok:
			self.tag_errors.append("Album arist and title required for MusicBrainz validation")
			return

		artist = self.tracks[0].get_flattened('ALBUMARTIST')
		album = self.tracks[0].get_tag('ALBUM')
		date = self.tracks[0].get_tag('DATE')

		results = musicbrainzngs.search_releases(album, artist=artist, limit=10)

		release = results['release-list'][0]
		curr_release = results['release-list']
		for release in results['release-list']:

			if release['ext:score'] != "100":
				continue

			if len(release['artist-credit'][0]) > 1:
				continue

			print (json.dumps(release, sort_keys=True, indent=4))
			mb_album = release['title']
			mb_date = release['date']
			mb_artist = release['artist-credit'][0]['artist']['name']

			print("{0} -> {1}".format(artist, mb_artist))
			print("{0} -> {1}".format(album, mb_album))
			print("{0} -> {1}".format(date, mb_date))






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

				# allow for broken/hacked LAME versions, treat as regular VBR
				try:
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
				except:
					self.method = "VBR"

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
	bitrate = None
	mp3info = None

	def get_filename(self):
		return self.path.split(os.path.sep)[-1]

	def __init__(self, path):
		self.path = path
		self.mp3info =  Mp3Info(path)
		self.metadata = taglib.File(path)
		self.bitrate = self.metadata.bitrate
		self.initial_clean()

	# checks for whitespace in tags and autofixes
	def initial_clean(self):

		write = False
		for tag in self.metadata.tags:
			for i in range(0, len(self.metadata.tags[tag])):
				if self.metadata.tags[tag][i] != clean_text(self.metadata.tags[tag][i]):
					self.metadata.tags[tag][i] = clean_text(self.metadata.tags[tag][i])
					write = True

		if write:
			self.metadata.save()


	def get_tag (self, tag, full=False):
		if tag in self.metadata.tags:

			# if there are duplicate matching tags, purge all but one
			self.clean_multiple_tags(tag)

			if len(self.metadata.tags[tag]):
				if full:
					return self.metadata.tags[tag]
				else:
					return self.metadata.tags[tag][0]

		return False


	def write_tag(self, tag, value):
		self.metadata.tags[tag] = value
		retval = self.metadata.save()
		if len(retval) != 0:
			print("Could not alter track tag: {0}".format(self.metadata))
			exit()

	def get_flattened(self, tag):

		acc = ""

		total = len(self.metadata.tags[tag])

		if total == 1:
			return self.metadata.tags[tag][0]
		
		acc = self.metadata.tags[tag][0]

		for i in range(1, total):
			while i < total - 1:
				acc += ", " + self.metadata.tags[tag][i]

		acc += " & " + self.metadata.tags[tag][-1]

		return acc

	def clean_multiple_tags(self, tag):

		if len(self.metadata.tags[tag]) in [0,1]:
			return

		new_tag_val = []
		for i in self.metadata.tags[tag]:
			if i != "":
				new_tag_val.append(i)

		# if we now have 0 or 1 tags, write out
		if len(new_tag_val) in [0,1]:
			pass

		# allow multiple fields in artist/albumartist
		if tag in ['ARTIST', 'ALBUMARTIST']:
			pass

		elif tag == 'DATE':
			new_tag_val = [sorted(self.metadata.tags[tag])[0]]

		else:
			curr = self.metadata.tags[tag][0]
			for i in self.metadata.tags[tag][1:]:
				if i != curr:
					print("|".join(self.metadata.tags[tag]))
					raise ValueError("Multitag on {0}: {1}".format(tag, self))
			new_tag_val = [self.metadata.tags[tag][0]]

		if self.metadata.tags[tag] != new_tag_val:
			self.write_tag(tag, new_tag_val)


	def close(self):
		self.metadata.close()


	def __repr__(self):
		return self.get_filename()
	def __eq__(self, other):
		return self.get_filename() == other.get_filename()
	def __gt__(self, other):
		return self.get_filename() > other.get_filename()

allowed_extensions = [".mp3", ".flac", ".jpg", ".jpeg", ".png", ".log", ".mix"]

def clean_text(text):
	return re.sub(' +', ' ', text.strip())

def nt_path_fix(path):
	if os.name != "nt":
		return path

	mapping = {	'\\':'_', '/':'_', ':':'：', '*':'', '?':'_', '"':'\'', '<':'[', '>':']', '|':'_'}
	for i in mapping:
		path = path.replace(i, mapping[i])

	return path

