# Import standard library modules for file system operations, external command execution,
# command-line argument parsing, date/time handling, JSON processing, and path manipulation.
import os
import shutil
import subprocess
import argparse
import datetime
import json
# Import type hinting support for lists and tuples to improve code clarity and static analysis.
from typing import List, Tuple
# Import Path from pathlib for modern, cross-platform path handling.
from pathlib import Path
# Import sys for system-specific parameters and functions, like stdout.
import sys

# Define a constant list of supported audio file extensions in lowercase.
# These are the file types the script recognizes as audio files for processing.
AUDIO_EXTENSIONS = ['.flac', '.wav', '.m4a', '.mp3', '.ogg', '.opus', '.ape', '.wv', '.wma']

# Define the configuration file path as a Path object.
# This file stores persistent settings, such as the log folder location.
CONFIG_FILE = Path("audio-script-config.json")

# Function to display a simple ASCII progress bar in the terminal.
def print_progress_bar(current: int, total: int, task_name: str = ''):
    """Displays a simple ASCII progress bar in the terminal."""
    # Set the fixed length of the progress bar to 70 characters.
    BAR_LENGTH = 70
    # Calculate the percentage completed, avoiding division by zero.
    percentage = (current / total) * 100 if total > 0 else 100
    # Calculate how many bar segments should be filled based on progress.
    filled = int(BAR_LENGTH * current // total) if total > 0 else BAR_LENGTH
    # Create the bar string: '#' for completed, '-' for remaining.
    bar = '#' * filled + '-' * (BAR_LENGTH - filled)
    # Print the progress bar with task name, bar, percentage, and current/total count.
    # '\r' returns the cursor to the start of the line for overwriting, 'flush=True' ensures immediate display.
    print(f'\r{task_name} [{bar}] {int(percentage)}% {current}/{total}', end='', flush=True)
    # If the task is complete, add a newline to finalize the output.
    if current == total:
        print()

# Custom argparse type function to validate that a path is a directory.
def directory_path(path: str) -> str:
    """Validates that a path is a directory."""
    # Check if the path exists and is a directory.
    if os.path.isdir(path):
        # Return the path if valid.
        return path
    # Raise an error with a descriptive message if the path is not a directory.
    raise argparse.ArgumentTypeError(f"'{path}' is not a directory")

# Custom argparse type function to validate that a path exists.
def path_type(path: str) -> str:
    """Validates that a path exists."""
    # Check if the path exists (can be a file or directory).
    if os.path.exists(path):
        # Return the path if it exists.
        return path
    # Raise an error with a descriptive message if the path does not exist.
    raise argparse.ArgumentTypeError(f"'{path}' does not exist")

# Function to recursively find all audio files in a directory.
def get_audio_files(directory: str) -> List[str]:
    """Recursively finds all audio files in a directory."""
    # Initialize an empty list to store paths of audio files.
    audio_files = []
    # Use os.walk to iterate over the directory tree (root, subdirs, files).
    for root, _, files in os.walk(directory):
        # Iterate over each file in the current directory.
        for file in files:
            # Split the file into name and extension, and convert extension to lowercase.
            # Check if the extension matches any in AUDIO_EXTENSIONS.
            if os.path.splitext(file)[1].lower() in AUDIO_EXTENSIONS:
                # Construct the full path and append it to the list.
                audio_files.append(os.path.join(root, file))
    # Return the list of audio file paths.
    return audio_files

# Function to check the integrity of an audio file using FFmpeg.
def check_file_integrity(file_path: str) -> Tuple[str, str]:
    """Uses FFmpeg to check audio file integrity."""
    try:
        # Run FFmpeg in error-only mode (-v error) with the input file (-i file_path).
        # Output to null format (-f null) and discard (-), capturing output as text.
        result = subprocess.run(
            ['ffmpeg', '-v', 'error', '-i', file_path, '-f', 'null', '-'],
            capture_output=True, text=True
        )
        # If no error output (stderr), the file is valid; return "PASSED" with empty message.
        # Otherwise, return "FAILED" with the stripped error message.
        return ("PASSED", "") if not result.stderr else ("FAILED", result.stderr.strip())
    except Exception as e:
        # If an exception occurs (e.g., FFmpeg not found), return "FAILED" with the exception message.
        return ("FAILED", str(e))

# Function to load or create the configuration file.
def load_config():
    """Loads or creates the config file."""
    # Check if the config file exists.
    if CONFIG_FILE.exists():
        # Open the file in read mode and load its JSON contents.
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        # If it doesn’t exist, define a default config with a log folder setting.
        default_config = {"log_folder": "Logs"}
        # Open the file in write mode and save the default config with indentation.
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)
        # Return the default config.
        return default_config

# Function to check the integrity of audio files in the given path.
def check_integrity(path: str, verbose: bool = False, summary: bool = False, save_log: bool = False, log_folder: Path = Path("Logs")):
    """Checks integrity of audio files."""
    # Check if FFmpeg is available in the system’s PATH.
    if not shutil.which('ffmpeg'):
        # Print an error and exit if FFmpeg is not found.
        print("Error: FFmpeg is not installed or not in your PATH.")
        return

    # Determine the list of audio files to process based on the input path.
    if os.path.isfile(path):
        # If the path is a file, check if it’s an audio file by extension.
        if os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS:
            audio_files = [path]
        else:
            # Print an error and exit if it’s not a supported audio file.
            print(f"'{path}' is not a supported audio file.")
            return
    elif os.path.isdir(path):
        # If the path is a directory, get all audio files recursively.
        audio_files = get_audio_files(path)
        # If no audio files are found, print a message and exit.
        if not audio_files:
            print(f"No audio files found in '{path}'.")
            return
    else:
        # If the path is neither a file nor directory, print an error and exit.
        print(f"'{path}' is not a file or directory.")
        return

    # Decide whether to create a log file: if save_log is True or neither verbose nor summary is set.
    create_log = save_log or (not verbose and not summary)
    log_file = None
    if create_log:
        # Create the log folder if it doesn’t exist, including parent directories.
        log_folder.mkdir(parents=True, exist_ok=True)
        # Generate a unique log filename with a timestamp.
        log_filename = log_folder / f"integrity_check_log_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
        # Open the log file in write mode with UTF-8 encoding.
        log_file = open(log_filename, 'w', encoding='utf-8')

    # Initialize counters for passed and failed files.
    passed_count = 0
    failed_count = 0
    # Get the total number of files to process.
    total_files = len(audio_files)

    # If not in verbose mode, initialize the progress bar at 0.
    if not verbose:
        print_progress_bar(0, total_files, "Checking files")

    # Iterate over each audio file with its index for progress tracking.
    for index, file_path in enumerate(audio_files):
        # Check the file’s integrity using FFmpeg.
        status, message = check_file_integrity(file_path)
        # Construct the result string: status, file path, and optional error message.
        result_line = f"{status} {file_path}" + (f": {message}" if message else "")

        # If verbose mode is enabled, print the result immediately.
        if verbose:
            print(result_line)
        # If logging is enabled, write the result to the log file.
        if create_log:
            log_file.write(result_line + "\n")

        # Increment the appropriate counter based on the status.
        if status == "PASSED":
            passed_count += 1
        else:
            failed_count += 1

        # If not in verbose mode, update the progress bar.
        if not verbose:
            print_progress_bar(index + 1, total_files, "Checking files")

    # Create a summary string with total, passed, and failed counts.
    summary_text = f"\nSummary:\nTotal files: {total_files}\nPassed: {passed_count}\nFailed: {failed_count}\n"
    # Print the summary if verbose or summary mode is enabled.
    if verbose or summary:
        print(summary_text)
    # If logging, write the summary to the log file and close it.
    if create_log:
        log_file.write(summary_text)
        log_file.close()
        # Inform the user where the log was saved.
        print(f"Check complete. Log saved to '{log_filename}'")
    else:
        # Otherwise, just indicate completion.
        print("Check complete.")

# Function to rename cover art files to hide or show them.
def rename_cover_art(file_path: str, hide: bool):
    """Renames cover art files to hide or show."""
    # Extract the file name and directory from the full path.
    file_name = os.path.basename(file_path)
    directory = os.path.dirname(file_path)
    # If hiding and the file is a standard cover art file...
    if hide and file_name in ["cover.jpg", "cover.jpeg", "cover.png"]:
        # Create a new hidden file name by adding a dot prefix.
        new_name = os.path.join(directory, "." + file_name)
        # Rename the file if the new name doesn’t already exist.
        if not os.path.exists(new_name):
            os.rename(file_path, new_name)
    # If showing and the file is a hidden cover art file...
    elif not hide and file_name in [".cover.jpg", ".cover.jpeg", ".cover.png"]:
        # Create a new visible file name by removing the dot prefix.
        new_name = os.path.join(directory, file_name[1:])
        # Rename the file if the new name doesn’t already exist.
        if not os.path.exists(new_name):
            os.rename(file_path, new_name)

# Function to process cover art files in a directory.
def process_cover_art(path: str, hide: bool):
    """Processes cover art files in a directory."""
    # Calculate the total number of files in the directory tree.
    total_files = sum(len(files) for _, _, files in os.walk(path))
    # If no files are found, print a message and exit.
    if total_files == 0:
        print(f"No files found in '{path}' to process.")
        return

    # Initialize a counter for processed files.
    processed = 0
    # Initialize the progress bar at 0.
    print_progress_bar(processed, total_files, "Processing cover art")
    # Walk through the directory tree.
    for root, _, files in os.walk(path):
        # Process each file in the current directory.
        for file in files:
            # Attempt to rename the file if it’s a cover art file.
            rename_cover_art(os.path.join(root, file), hide)
            # Increment the processed counter.
            processed += 1
            # Update the progress bar.
            print_progress_bar(processed, total_files, "Processing cover art")

# Function to analyze audio file metadata using ffprobe.
def analyze_audio(path: str, output_stream, show_progress: bool = True):
    """Analyzes audio file metadata."""
    # Check if ffprobe is available in the system’s PATH.
    if not shutil.which('ffprobe'):
        # Print an error and exit if ffprobe is not found.
        print("Error: ffprobe is not installed or not in your PATH.")
        return

    # Determine the list of audio files to analyze.
    if os.path.isfile(path):
        # If the path is a file, check if it’s an audio file.
        if os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS:
            audio_files = [Path(path)]
        else:
            # Print an error and exit if it’s not a supported audio file.
            print(f"'{path}' is not a supported audio file.")
            return
    elif os.path.isdir(path):
        # If the path is a directory, use Path.rglob to find all audio files recursively.
        audio_files = [file for ext in AUDIO_EXTENSIONS for file in Path(path).rglob(f"*{ext}")]
        # If no audio files are found, print a message and exit.
        if not audio_files:
            print(f"No audio files found in '{path}'.")
            return
    else:
        # If the path is neither a file nor directory, print an error and exit.
        print(f"'{path}' is not a file or directory.")
        return

    # Get the total number of files for progress tracking.
    total_files = len(audio_files)
    # If showing progress, initialize the progress bar at 0.
    if show_progress:
        print_progress_bar(0, total_files, "Analyzing audio")

    # Iterate over each audio file with its index for progress tracking.
    for index, audio_file in enumerate(audio_files):
        # Write the file being analyzed to the output stream.
        output_stream.write(f"Analyzing: {audio_file}\n")
        try:
            # Run ffprobe to get metadata in JSON format, suppressing verbose output.
            cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(audio_file)]
            result = subprocess.check_output(cmd, universal_newlines=True)
            # Parse the JSON output into a Python dictionary.
            data = json.loads(result)
            # Assume the first stream is the audio stream and extract it.
            stream = data["streams"][0]

            # Extract metadata fields, defaulting to "N/A" if not present.
            codec = stream.get("codec_name", "N/A")
            sample_rate = stream.get("sample_rate", "N/A")
            channels = stream.get("channels", "N/A")
            bit_depth = stream.get("bits_per_raw_sample", "N/A")
            bit_rate = data["format"].get("bit_rate", "N/A")

            # Determine channel information based on the number of channels.
            channel_info = "N/A" if channels == "N/A" else "Mono" if channels == 1 else "Stereo" if channels == 2 else f"{channels} channels"
            # Write metadata to the output stream, formatting units appropriately.
            output_stream.write(f"  Bitrate: {bit_rate} bps\n" if bit_rate != "N/A" else "  Bitrate: N/A\n")
            output_stream.write(f"  Sample Rate: {sample_rate} Hz\n" if sample_rate != "N/A" else "  Sample Rate: N/A\n")
            output_stream.write(f"  Bit Depth: {bit_depth} bits\n" if bit_depth != "N/A" else "  Bit Depth: N/A\n")
            output_stream.write(f"  Channels: {channel_info}\n")
            output_stream.write(f"  Codec: {codec}\n")

            # Add codec-specific information for .m4a files.
            if audio_file.suffix.lower() == ".m4a":
                if "aac" in codec.lower():
                    output_stream.write("  [INFO] AAC (lossy) codec detected.\n")
                elif "alac" in codec.lower():
                    output_stream.write("  [INFO] ALAC (lossless) codec detected.\n")
                else:
                    output_stream.write(f"  [WARNING] Unknown codec: {codec}\n")
            # Note lossy codecs for .opus and .mp3 files.
            elif audio_file.suffix.lower() in [".opus", ".mp3"]:
                output_stream.write(f"  [INFO] Lossy codec: {codec}\n")
            # Warn if bit depth is less than 16, suggesting possible lossy encoding.
            if bit_depth != "N/A" and int(bit_depth) < 16:
                output_stream.write("  [WARNING] Low bit depth may indicate lossy encoding.\n")
            # Warn if sample rate is less than 44.1 kHz, suggesting possible lossy encoding.
            if sample_rate != "N/A" and int(sample_rate) < 44100:
                output_stream.write("  [WARNING] Low sample rate may indicate lossy encoding.\n")
            # Add a blank line for readability.
            output_stream.write("\n")
        except Exception as e:
            # If analysis fails, write an error message to the output stream.
            output_stream.write(f"  [ERROR] Failed to analyze: {e}\n")

        # If showing progress, update the progress bar.
        if show_progress:
            print_progress_bar(index + 1, total_files, "Analyzing audio")

# Main function to set up the command-line interface and dispatch commands.
def main():
    """Sets up argparse and dispatches commands."""
    # Load the configuration from the config file or create it.
    config = load_config()
    # Get the log folder path from the config, defaulting to "Logs".
    log_folder = Path(config.get("log_folder", "Logs"))

    # Initialize the argument parser with a description.
    parser = argparse.ArgumentParser(description="Tool for managing audio files")
    # Add subparsers for different commands, making a command required.
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    # Define the 'check' subcommand for verifying audio file integrity.
    check_parser = subparsers.add_parser("check", help="Verify audio file integrity")
    # Add a required argument for the path to check, using the custom path_type validator.
    check_parser.add_argument("path", type=path_type, help="File or directory to check")
    # Create a mutually exclusive group for output options (verbose and summary can’t coexist).
    output_group = check_parser.add_mutually_exclusive_group()
    # Add a flag for verbose output, disabling the progress bar.
    output_group.add_argument("--verbose", action="store_true", help="Print detailed results to console (no progress bar)")
    # Add a flag for summary output, showing only the progress bar and final summary.
    output_group.add_argument("--summary", action="store_true", help="Show progress bar and summary only")
    # Add a flag to save results to a log file.
    check_parser.add_argument("--save-log", action="store_true", help="Save results to a log file")

    # Define the 'cover-art' subcommand for hiding or showing cover art files.
    cover_parser = subparsers.add_parser("cover-art", help="Hide or show cover art files")
    # Create a mutually exclusive group for hide/show options, requiring one to be specified.
    cover_group = cover_parser.add_mutually_exclusive_group(required=True)
    # Add a flag to hide cover art by adding a dot prefix.
    cover_group.add_argument("--hide", action="store_true", help="Hide cover art by adding a dot prefix")
    # Add a flag to show cover art by removing the dot prefix.
    cover_group.add_argument("--show", action="store_true", help="Show cover art by removing dot prefix")
    # Add a required argument for the directory to process, using the directory_path validator.
    cover_parser.add_argument("path", type=directory_path, help="Directory to process")

    # Define the 'info' subcommand for analyzing audio file metadata.
    info_parser = subparsers.add_parser("info", help="Analyze audio file metadata")
    # Add a required argument for the path to analyze, using the path_type validator.
    info_parser.add_argument("path", type=path_type, help="File or directory to analyze")
    # Add an optional argument for the output file, defaulting to "audio_analysis.txt".
    info_parser.add_argument("-o", "--output", default="audio_analysis.txt", help="Output file for results")
    # Add a flag for verbose output, disabling the progress bar.
    info_parser.add_argument("--verbose", action="store_true", help="Print results to console (no progress bar)")

    # Parse the command-line arguments.
    args = parser.parse_args()

    # Dispatch to the appropriate function based on the command provided.
    if args.command == "check":
        # Call check_integrity with the parsed arguments and log folder.
        check_integrity(args.path, verbose=args.verbose, summary=args.summary, save_log=args.save_log, log_folder=log_folder)
    elif args.command == "cover-art":
        # Call process_cover_art with the path and hide flag (True for --hide, False for --show).
        process_cover_art(args.path, hide=args.hide)
    elif args.command == "info":
        if args.verbose:
            # If verbose, analyze audio and output to stdout without progress.
            analyze_audio(args.path, sys.stdout, show_progress=False)
        else:
            # Otherwise, use the specified output file, adding a timestamp if it’s the default.
            output_file = args.output
            if output_file == "audio_analysis.txt":
                output_file = f"audio_analysis_{datetime.datetime.now().strftime('%Y%m%d')}.txt"
            # Open the output file and analyze audio, writing results to it.
            with open(output_file, "w") as f:
                analyze_audio(args.path, f)
            # Inform the user where the results were saved.
            print(f"Analysis complete. Results saved to '{output_file}'")

# Standard Python idiom to run the main function when the script is executed directly.
if __name__ == "__main__":
    try:
        # Execute the main function.
        main()
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully by printing a quitting message.
        print("Quitting job...")
