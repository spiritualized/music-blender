import argparse
import os
from colorama import Fore, Back, Style, init as colorama_init

allowed_extensions = [".mp3", ".flac", ".jpg", ".jpeg"]

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
			disallowed_files.append(i)
	return disallowed_files

def validate_folder(folder):

	failure_reasons = []

	if check_subfolders(folder):
		failure_reasons.append("Subfolder present")

	disallowed_files = check_disallowed_files(folder)
	for file in disallowed_files:
		failure_reasons.append("Disallowed file: {0}".format(file))

	return failure_reasons

def string_colour(string, color):
	return "".join([color, string, Style.RESET_ALL])
def string_background(string, color):
	return "".join([color, string, Style.RESET_ALL])

#colorama
colorama_init(autoreset=True)

#argparse
parser = argparse.ArgumentParser(description='Validate a music collection.')
parser.add_argument('source', metavar='source', type=str,
                   help='Top level folder containing all albums')
parser.add_argument('destination', metavar='destination', type=str,
                   help='Folder to move all validated albums')
args = parser.parse_args()

source = args.source
destination = args.destination

folders = os.listdir(source)
print("Scanning {0} subfolders...".format(len(folders)))

last_failed = False

for curr in folders:

	full_path = os.path.join(source, curr)

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