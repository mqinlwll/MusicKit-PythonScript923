import os                    # Handles file and directory operations like listing files or checking paths
import shutil                # Used to check if external tools (e.g., FFmpeg) are available in the system PATH
import subprocess            # Runs external commands like FFmpeg and ffprobe, capturing their output
import argparse              # Parses command-line arguments to allow user inputs like paths or flags
import datetime              # Generates timestamps for naming log/output files uniquely
import json                  # Parses JSON output from ffprobe for metadata extraction
from typing import List, Tuple  # Adds type hints for better code readability and IDE support
from pathlib import Path     # Modern way to handle file paths, works across Windows, Linux, macOS
import sys                   # Access to stdout for printing verbose output directly to console

# Define supported audio file extensions as a constant for consistent use across the script
AUDIO_EXTENSIONS = ['.flac', '.wav', '.m4a', '.mp3', '.ogg', '.opus', '.ape', '.wv', '.wma']

def print_progress_bar(current: int, total: int, task_name: str = ''):
    """Displays a simple ASCII progress bar in the terminal to show task progress."""
    BAR_LENGTH = 70  # Fixed width of the bar in characters for consistent display
    percentage = (current / total) * 100 if total > 0 else 100  # Calculate completion percentage, avoid dividing by zero
    filled = int(BAR_LENGTH * current // total) if total > 0 else BAR_LENGTH  # Number of '#' characters to show progress
    bar = '#' * filled + '-' * (BAR_LENGTH - filled)  # Construct the bar: '#' for done, '-' for remaining
    # Print the bar with task name, percentage, and current/total, using '\r' to overwrite the line
    print(f'\r{task_name} [{bar}] {int(percentage)}% {current}/{total}', end='', flush=True)
    if current == total:  # When task is complete, add a newline to finalize the output
        print()

def directory_path(path: str) -> str:
    """Validates that a given path is a directory for argparse to ensure correct input."""
    if os.path.isdir(path):  # Check if the path is a directory
        return path  # Return it if valid
    # Raise an error if not a directory, which argparse will display to the user
    raise argparse.ArgumentTypeError(f"'{path}' is not a directory")

def path_type(path: str) -> str:
    """Validates that a given path exists (file or directory) for argparse."""
    if os.path.exists(path):  # Check if the path exists on the filesystem
        return path  # Return it if valid
    # Raise an error if it doesn’t exist, informing the user
    raise argparse.ArgumentTypeError(f"'{path}' does not exist")

def get_audio_files(directory: str) -> List[str]:
    """Recursively finds all audio files in a directory with supported extensions."""
    audio_files = []  # List to store paths of audio files
    for root, _, files in os.walk(directory):  # Walk through directory and subdirectories
        for file in files:  # Iterate over files in each directory
            # Split file into name and extension, check if extension (lowercase) is supported
            if os.path.splitext(file)[1].lower() in AUDIO_EXTENSIONS:
                audio_files.append(os.path.join(root, file))  # Add full path to the list
    return audio_files  # Return the complete list of audio file paths

def check_file_integrity(file_path: str) -> Tuple[str, str]:
    """Uses FFmpeg to check if an audio file is intact or corrupted."""
    try:
        # Run FFmpeg with error-only logging (-v error), input file (-i), and null output (-f null)
        result = subprocess.run(
            ['ffmpeg', '-v', 'error', '-i', file_path, '-f', 'null', '-'],
            capture_output=True, text=True  # Capture output as text for processing
        )
        # If no errors in stderr, file is good; return "PASSED" with empty message
        return ("PASSED", "") if not result.stderr else ("FAILED", result.stderr.strip())
    except Exception as e:  # Handle cases like FFmpeg not found or other errors
        return ("FAILED", str(e))  # Return "FAILED" with the error message

def check_integrity(path: str, verbose: bool = False, save_log: bool = False):
    """Checks integrity of audio files in a given path, with options for verbosity and logging."""
    if not shutil.which('ffmpeg'):  # Check if FFmpeg is available in PATH
        print("Error: FFmpeg is not installed or not in your PATH.")
        return  # Exit if FFmpeg isn’t found

    # Handle single file or directory input
    if os.path.isfile(path):  # If path is a file
        if os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS:  # Check if it’s an audio file
            audio_files = [path]  # List with just this file
        else:
            print(f"'{path}' is not a supported audio file.")  # Inform user if unsupported
            return
    elif os.path.isdir(path):  # If path is a directory
        audio_files = get_audio_files(path)  # Get all audio files recursively
        if not audio_files:  # If no audio files found
            print(f"No audio files found in '{path}'.")
            return
    else:  # If path is neither file nor directory
        print(f"'{path}' is not a file or directory.")
        return

    # Set up logging if requested or if not verbose (default behavior)
    log_file = None
    if save_log or not verbose:  # Log unless verbose is True and save_log is False
        # Create a unique log filename with current timestamp
        log_filename = f"integrity_check_log_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
        log_file = open(log_filename, 'w', encoding='utf-8')  # Open file for writing

    # Initialize counters for summary
    passed_count = 0
    failed_count = 0
    total_files = len(audio_files)

    if not verbose:  # Show progress bar unless verbose mode is on
        print_progress_bar(0, total_files, "Checking files")

    # Process each audio file
    for index, file_path in enumerate(audio_files):
        status, message = check_file_integrity(file_path)  # Check file integrity
        # Construct result line with status, path, and optional error message
        result_line = f"{status} {file_path}" + (f": {message}" if message else "")

        if verbose:  # Print to console if verbose mode is enabled
            print(result_line)
        if log_file:  # Write to log file if logging is enabled
            log_file.write(result_line + "\n")

        # Update counters based on status
        if status == "PASSED":
            passed_count += 1
        else:
            failed_count += 1

        if not verbose:  # Update progress bar if not in verbose mode
            print_progress_bar(index + 1, total_files, "Checking files")

    # Create summary of results
    summary = f"\nSummary:\nTotal files: {total_files}\nPassed: {passed_count}\nFailed: {failed_count}\n"
    if verbose:  # Print summary to console in verbose mode
        print(summary)
    if log_file:  # Write summary to log file and close it
        log_file.write(summary)
        log_file.close()
        print(f"Check complete. Log saved to '{log_filename}'")  # Inform user of log location
    else:
        print("Check complete.")  # Simple completion message if no log

def rename_cover_art(file_path: str, hide: bool):
    """Renames cover art files to hide (add dot) or show (remove dot)."""
    file_name = os.path.basename(file_path)  # Get just the filename
    directory = os.path.dirname(file_path)  # Get the directory path

    # If hiding and file is a cover art file
    if hide and file_name in ["cover.jpg", "cover.jpeg", "cover.png"]:
        new_name = os.path.join(directory, "." + file_name)  # Add dot prefix
        if not os.path.exists(new_name):  # Only rename if target doesn’t exist
            os.rename(file_path, new_name)
    # If showing and file is a hidden cover art file
    elif not hide and file_name in [".cover.jpg", ".cover.jpeg", ".cover.png"]:
        new_name = os.path.join(directory, file_name[1:])  # Remove dot prefix
        if not os.path.exists(new_name):  # Only rename if target doesn’t exist
            os.rename(file_path, new_name)

def process_cover_art(path: str, hide: bool):
    """Processes cover art files in a directory, showing progress."""
    # Count total files for progress bar
    total_files = sum(len(files) for _, _, files in os.walk(path))
    if total_files == 0:  # If no files found
        print(f"No files found in '{path}' to process.")
        return

    processed = 0  # Track number of files processed
    print_progress_bar(processed, total_files, "Processing cover art")  # Initial bar

    # Walk through directory and process cover art files
    for root, _, files in os.walk(path):
        for file in files:
            rename_cover_art(os.path.join(root, file), hide)  # Rename if applicable
            processed += 1  # Increment processed count
            print_progress_bar(processed, total_files, "Processing cover art")  # Update bar

def analyze_audio(path: str, output_stream, show_progress: bool = True):
    """Analyzes audio file metadata using ffprobe and writes results."""
    if not shutil.which('ffprobe'):  # Check if ffprobe is available
        print("Error: ffprobe is not installed or not in your PATH.")
        return

    # Collect audio files based on path type
    if os.path.isfile(path):  # If single file
        if os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS:
            audio_files = [Path(path)]  # Use Path for modern path handling
        else:
            print(f"'{path}' is not a supported audio file.")
            return
    elif os.path.isdir(path):  # If directory
        # Use Path.rglob to recursively find audio files with supported extensions
        audio_files = [file for ext in AUDIO_EXTENSIONS for file in Path(path).rglob(f"*{ext}")]
        if not audio_files:
            print(f"No audio files found in '{path}'.")
            return
    else:
        print(f"'{path}' is not a file or directory.")
        return

    total_files = len(audio_files)  # Total files for progress
    if show_progress:  # Show initial progress bar if enabled
        print_progress_bar(0, total_files, "Analyzing audio")

    # Process each audio file
    for index, audio_file in enumerate(audio_files):
        output_stream.write(f"Analyzing: {audio_file}\n")  # Write file being analyzed
        try:
            # Run ffprobe to get metadata in JSON format
            cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(audio_file)]
            result = subprocess.check_output(cmd, universal_newlines=True)  # Get output as text
            data = json.loads(result)  # Parse JSON
            stream = data["streams"][0]  # Assume first stream is audio

            # Extract metadata with fallback values if missing
            codec = stream.get("codec_name", "N/A")
            sample_rate = stream.get("sample_rate", "N/A")
            channels = stream.get("channels", "N/A")
            bit_depth = stream.get("bits_per_raw_sample", "N/A")
            bit_rate = data["format"].get("bit_rate", "N/A")

            # Format channel information for readability
            if channels == "N/A":
                channel_info = "N/A"
            elif channels == 1:
                channel_info = "Mono"
            elif channels == 2:
                channel_info = "Stereo"
            else:
                channel_info = f"{channels} channels"

            # Write metadata to output stream
            output_stream.write(f"  Bitrate: {bit_rate} bps\n" if bit_rate != "N/A" else "  Bitrate: N/A\n")
            output_stream.write(f"  Sample Rate: {sample_rate} Hz\n" if sample_rate != "N/A" else "  Sample Rate: N/A\n")
            output_stream.write(f"  Bit Depth: {bit_depth} bits\n" if bit_depth != "N/A" else "  Bit Depth: N/A\n")
            output_stream.write(f"  Channels: {channel_info}\n")
            output_stream.write(f"  Codec: {codec}\n")

            # Add codec-specific information or warnings
            if audio_file.suffix.lower() == ".m4a":
                if "aac" in codec.lower():
                    output_stream.write("  [INFO] AAC (lossy) codec detected.\n")
                elif "alac" in codec.lower():
                    output_stream.write("  [INFO] ALAC (lossless) codec detected.\n")
                else:
                    output_stream.write(f"  [WARNING] Unknown codec: {codec}\n")
            elif audio_file.suffix.lower() in [".opus", ".mp3"]:
                output_stream.write(f"  [INFO] Lossy codec: {codec}\n")

            # Check for quality warnings
            if bit_depth != "N/A" and int(bit_depth) < 16:
                output_stream.write("  [WARNING] Low bit depth may indicate lossy encoding.\n")
            if sample_rate != "N/A" and int(sample_rate) < 44100:
                output_stream.write("  [WARNING] Low sample rate may indicate lossy encoding.\n")

            output_stream.write("\n")  # Blank line for readability
        except Exception as e:  # Handle errors like ffprobe failure
            output_stream.write(f"  [ERROR] Failed to analyze: {e}\n")

        if show_progress:  # Update progress bar if enabled
            print_progress_bar(index + 1, total_files, "Analyzing audio")

def main():
    """Sets up argparse and dispatches commands based on user input."""
    parser = argparse.ArgumentParser(description="Tool for managing audio files")  # Main parser
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)  # Subcommands

    # 'check' command setup
    check_parser = subparsers.add_parser("check", help="Verify audio file integrity")
    check_parser.add_argument("path", type=path_type, help="File or directory to check")
    check_parser.add_argument("--verbose", action="store_true", help="Print results to console (no progress bar)")
    check_parser.add_argument("--save-log", action="store_true", help="Save results to a log file")

    # 'cover-art' command setup
    cover_parser = subparsers.add_parser("cover-art", help="Hide or show cover art files")
    cover_group = cover_parser.add_mutually_exclusive_group(required=True)  # Mutually exclusive hide/show
    cover_group.add_argument("--hide", action="store_true", help="Hide cover art by adding a dot prefix")
    cover_group.add_argument("--show", action="store_true", help="Show cover art by removing dot prefix")
    cover_parser.add_argument("path", type=directory_path, help="Directory to process")

    # 'info' command setup
    info_parser = subparsers.add_parser("info", help="Analyze audio file metadata")
    info_parser.add_argument("path", type=path_type, help="File or directory to analyze")
    info_parser.add_argument("-o", "--output", default="audio_analysis.txt", help="Output file for results")
    info_parser.add_argument("--verbose", action="store_true", help="Print results to console (no progress bar)")

    args = parser.parse_args()  # Parse command-line arguments

    # Dispatch to the appropriate function based on command
    if args.command == "check":
        check_integrity(args.path, verbose=args.verbose, save_log=args.save_log)
    elif args.command == "cover-art":
        process_cover_art(args.path, hide=args.hide)
    elif args.command == "info":
        if args.verbose:  # Output to console if verbose
            analyze_audio(args.path, sys.stdout, show_progress=False)
        else:  # Otherwise, write to a file
            output_file = args.output
            if output_file == "audio_analysis.txt":  # Add timestamp to default filename
                output_file = f"audio_analysis_{datetime.datetime.now().strftime('%Y%m%d')}.txt"
            with open(output_file, "w") as f:  # Open file for writing
                analyze_audio(args.path, f)  # Analyze and write to file
            print(f"Analysis complete. Results saved to '{output_file}'")  # Inform user

if __name__ == "__main__":
    """Entry point of the script, runs main() and handles interruptions."""
    try:
        main()  # Run the main function
    except KeyboardInterrupt:  # Catch Ctrl+C
        print("Quitting job...")  # Graceful exit message
