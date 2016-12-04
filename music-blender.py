import os
import argparse
from colorama import Fore, Back, Style, init as colorama_init
import mblib


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

parser.add_argument('source', metavar='directory', type=str,
                   help='Top level folder containing all albums')
parser.add_argument('--move-to', metavar='destination', type=str,
                   help='Move folders which pass validation to this destination')
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
parser.add_argument('--fix-filenames', action='store_true',
                   help='Validate filenames')
parser.add_argument('--fix-foldernames', action='store_true',
                   help='Validate folder names')


args = parser.parse_args()

source = args.source
blender = mblib.blender()

if args.move_to:
	blender.set_move_to(args.move_to)


blender.delete_disallowed_files = args.delete_disallowed_files
blender.fix_track_numbers = args.fix_track_numbers
blender.fix_track_number_of = args.fix_track_number_of
blender.fix_album_artist = args.fix_album_artist
blender.fix_year = args.fix_year
blender.fix_disc_numbers = args.fix_disc_numbers
blender.fix_disc_number_of = args.fix_disc_number_of
blender.fix_filenames = args.fix_filenames
blender.fix_foldernames = args.fix_foldernames

if not os.path.isdir(source):
	print("Source folder {0} does not exist".format(source))
	exit()

folders = os.listdir(source)
print("Scanning {0} subfolders...".format(len(folders)))

last_failed = False

total_failure_reasons = 0

for curr in folders:

	full_path = os.path.join(source, curr)

	# skip files in the root folder
	if not os.path.isdir(full_path):
		continue

	blender.open_folder(full_path)

	failure_reasons = blender.validate_folder()
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
# tracknumber check on multi CD
# implement musicCRC?
# 8 bit people