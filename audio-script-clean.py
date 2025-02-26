import os
import shutil
import subprocess
import argparse
import datetime
import json
from typing import List, Tuple
from pathlib import Path
import sys  # Added for sys.stdout in verbose mode

# Custom progress bar function
def print_progress_bar(iteration, total, description=''):
    """Display a simple ASCII progress bar in the terminal.
    Args:
        iteration (int): Current iteration (0 to total).
        total (int): Total number of iterations.
        description (str): Text to display before the progress bar (e.g., task name).
    Notes:
        - Uses '#' for completed portion and '-' for remaining.
        - Overwrites the same line in the terminal using '\r'.
    """
    bar_length = 70  # Fixed length of the progress bar in characters
    percentage = (iteration / total) * 100 if total > 0 else 100  # Calculate completion percentage
    filled_length = int(bar_length * iteration // total) if total > 0 else bar_length  # Filled portion
    bar = '#' * filled_length + '-' * (bar_length - filled_length)  # Construct the bar
    print(f'\r{description} [{bar}] {int(percentage)}% {iteration}/{total}', end='', flush=True)
    if iteration == total:
        print()  # Print a newline when complete to avoid overwriting

# Custom argument type for directories (used only for cover-art)
def directory_path(path):
    """Validate that a path is an existing directory.
    Args:
        path (str): Path to validate.
    Returns:
        str: The path if it's a directory.
    Raises:
        argparse.ArgumentTypeError: If the path is not a directory.
    """
    if os.path.isdir(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a directory")

# Custom argument type for any existing path (file or directory)
def path_type(path):
    """Validate that a path exists (can be a file or directory).
    Args:
        path (str): Path to validate.
    Returns:
        str: The path if it exists.
    Raises:
        argparse.ArgumentTypeError: If the path does not exist.
    """
    if os.path.exists(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} does not exist")

# Supported audio extensions (global for consistency)
AUDIO_EXTENSIONS = ['.flac', '.wav', '.m4a', '.mp3', '.ogg', '.opus', '.ape', '.wv', '.wma']
# List of file extensions considered as audio files, used across check and info commands

# Functions for 'check' subcommand
def get_audio_files(directory: str) -> List[str]:
    """Recursively find all audio files in a directory with supported extensions.
    Args:
        directory (str): Directory path to search.
    Returns:
        List[str]: List of full paths to audio files found.
    Notes:
        - Uses os.walk to traverse directory tree.
        - Matches files against AUDIO_EXTENSIONS (case-insensitive).
    """
    return [
        os.path.join(root, file)
        for root, _, files in os.walk(directory)
        for file in files
        if os.path.splitext(file)[1].lower() in AUDIO_EXTENSIONS
    ]

def check_file_integrity(file_path: str) -> Tuple[str, str]:
    """Use FFmpeg to verify the integrity of an audio file.
    Args:
        file_path (str): Path to the audio file to check.
    Returns:
        Tuple[str, str]: (status, message) where status is 'PASSED' or 'FAILED', message is error details if FAILED.
    Notes:
        - FFmpeg is run with error logging only (-v error), outputting to null (-f null).
        - Captures stderr for error messages.
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-v', 'error', '-i', file_path, '-f', 'null', '-'],
            capture_output=True,
            text=True
        )
        if result.stderr:
            return "FAILED", result.stderr.strip()  # Return error message if FFmpeg finds issues
        else:
            return "PASSED", ""  # No errors detected
    except Exception as e:
        return "FAILED", str(e)  # Handle exceptions (e.g., FFmpeg not found)

def check_integrity(path: str, verbose: bool = False, save_log: bool = False):
    """Check the integrity of audio file(s) and handle output based on flags.
    Args:
        path (str): Path to a single file or directory to check.
        verbose (bool): If True, print results to console and suppress progress bar.
        save_log (bool): If True with verbose, save results to log file; otherwise, log is saved if not verbose.
    Notes:
        - Supports both single files and directories.
        - Log file is created unless verbose is True and save_log is False.
    """
    if not shutil.which('ffmpeg'):  # Check if FFmpeg is installed and in PATH
        print("FFmpeg is not found. Please install FFmpeg and ensure it's in your PATH.")
        return

    # Determine if path is a file or directory and gather audio files
    if os.path.isfile(path):
        if os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS:
            audio_files = [path]  # Single file case
        else:
            print(f"{path} is not a supported audio file.")
            return
    elif os.path.isdir(path):
        audio_files = get_audio_files(path)  # Directory case
        if not audio_files:
            print("No audio files found in the specified directory.")
            return
    else:
        print(f"{path} is neither a file nor a directory.")
        return

    # Set up log file if required
    log_file = None
    if save_log or not verbose:  # Log is saved by default unless verbose is True and save_log is False
        log_filename = f"integrity_check_log_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
        log_file = open(log_filename, 'w', encoding='utf-8')

    passed_count = 0
    failed_count = 0
    total = len(audio_files)

    if not verbose:
        print_progress_bar(0, total, description="Checking files")  # Initial progress bar

    for i, file_path in enumerate(audio_files):
        status, message = check_file_integrity(file_path)
        status_line = f"{status} {file_path}" + (f": {message}" if message else "")

        if verbose:
            print(status_line)  # Print to console in verbose mode
        if log_file:
            log_file.write(status_line + "\n")  # Write to log file if open

        if status == "PASSED":
            passed_count += 1
        else:
            failed_count += 1

        if not verbose:
            print_progress_bar(i + 1, total, description="Checking files")  # Update progress bar

    summary = f"\nSummary:\nTotal files checked: {len(audio_files)}\nPassed: {passed_count}\nFailed: {failed_count}\n"
    if verbose:
        print(summary)  # Print summary to console in verbose mode
    if log_file:
        log_file.write(summary)  # Write summary to log file
        log_file.close()
        print(f"Check completed. Log saved to {log_filename}")
    else:
        print("Check completed.")  # Simple completion message if no log

# Functions for 'cover-art' subcommand
def rename_cover_art(file_path: str, hide: bool):
    """Rename cover art files to hide (add dot prefix) or show (remove dot prefix).
    Args:
        file_path (str): Full path to the file.
        hide (bool): True to hide (add dot), False to show (remove dot).
    Notes:
        - Only processes specific cover art filenames.
        - Avoids overwriting existing files.
    """
    file_name = os.path.basename(file_path)
    dir_path = os.path.dirname(file_path)
    if hide:
        if file_name in ["cover.jpg", "cover.jpeg", "cover.png"]:
            target_name = os.path.join(dir_path, "." + file_name)
            if not os.path.exists(target_name):
                os.rename(file_path, target_name)
    else:
        if file_name in [".cover.jpg", ".cover.jpeg", ".cover.png"]:
            original_name = os.path.join(dir_path, file_name[1:])
            if not os.path.exists(original_name):
                os.rename(file_path, original_name)

def process_cover_art(path: str, hide: bool):
    """Process all cover art files in a directory to hide or show them.
    Args:
        path (str): Directory path to process.
        hide (bool): True to hide cover art, False to show it.
    Notes:
        - Uses progress bar to show processing status.
        - Processes all files recursively.
    """
    total_files = sum(len(files) for _, _, files in os.walk(path))
    if total_files == 0:
        print("No files found in the specified directory to process.")
        return
    processed = 0
    print_progress_bar(processed, total_files, description="Processing cover art files")
    for root, _, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            rename_cover_art(file_path, hide)
            processed += 1
            print_progress_bar(processed, total_files, description="Processing cover art files")

# Function for 'info' subcommand
def analyze_audio(path: str, output_stream, show_progress: bool = True):
    """Analyze audio file properties and write results to output_stream.
    Args:
        path (str): Path to a file or directory to analyze.
        output_stream: File-like object (e.g., sys.stdout or open file) to write results.
        show_progress (bool): If True, display a progress bar.
    Notes:
        - Uses ffprobe to extract audio metadata.
        - Supports both single files and directories.
    """
    if not shutil.which('ffprobe'):
        print("ffprobe is not found. Please install FFmpeg and ensure ffprobe is in your PATH.")
        return

    # Gather audio files
    if os.path.isfile(path):
        if os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS:
            audio_files = [Path(path)]
        else:
            print(f"{path} is not a supported audio file.")
            return
    elif os.path.isdir(path):
        audio_files = []
        for ext in AUDIO_EXTENSIONS:
            audio_files.extend(Path(path).rglob("*" + ext))
        if not audio_files:
            print("No audio files found in the specified directory.")
            return
    else:
        print(f"{path} is neither a file nor a directory.")
        return

    total = len(audio_files)
    if show_progress:
        print_progress_bar(0, total, description="Analyzing audio files")

    for i, audio_file in enumerate(audio_files):
        output_stream.write(f"Analyzing: {audio_file}\n")
        try:
            # Run ffprobe to get metadata in JSON format
            command = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(audio_file)]
            output = subprocess.check_output(command, universal_newlines=True)
            data = json.loads(output)
            stream = data["streams"][0]  # Assume first stream is audio
            codec_name = stream.get("codec_name", "N/A")
            sample_rate = stream.get("sample_rate", "N/A")
            channels = stream.get("channels", "N/A")
            bit_depth = stream.get("bits_per_raw_sample", "N/A")
            format_data = data["format"]
            bit_rate = format_data.get("bit_rate", "N/A")
            channel_info = "Mono" if channels == 1 else "Stereo" if channels == 2 else f"{channels} channels" if channels != "N/A" else "N/A"
            # Write metadata to output
            output_stream.write(f"  Bitrate: {bit_rate} bps\n" if bit_rate != "N/A" else "  Bitrate: N/A\n")
            output_stream.write(f"  Sample Rate: {sample_rate} Hz\n" if sample_rate != "N/A" else "  Sample Rate: N/A\n")
            output_stream.write(f"  Bit Depth: {bit_depth} bits\n" if bit_depth != "N/A" else "  Bit Depth: N/A\n")
            output_stream.write(f"  Channels: {channel_info}\n")
            output_stream.write(f"  Codec: {codec_name}\n")
            # Add codec-specific info/warnings
            if audio_file.suffix == ".m4a":
                if "aac" in codec_name.lower():
                    output_stream.write("  [INFO] This is an AAC (lossy) file.\n")
                elif "alac" in codec_name.lower():
                    output_stream.write("  [INFO] This is an ALAC (lossless) file.\n")
                else:
                    output_stream.write(f"  [WARNING] Unknown codec: {codec_name}\n")
            elif audio_file.suffix in [".opus", ".mp3"]:
                output_stream.write(f"  [INFO] This is a lossy file: {codec_name}\n")
            if bit_depth != "N/A" and int(bit_depth) < 16:
                output_stream.write("  [WARNING] Potential lossy encoding: Low bit depth\n")
            if sample_rate != "N/A" and int(sample_rate) < 44100:
                output_stream.write("  [WARNING] Potential lossy encoding: Low sample rate\n")
            output_stream.write("\n")
        except subprocess.CalledProcessError:
            output_stream.write("  [ERROR] Failed to analyze file with ffprobe.\n")
        except json.JSONDecodeError:
            output_stream.write("  [ERROR] Failed to parse ffprobe output.\n")
        except Exception as e:
            output_stream.write(f"  [ERROR] {str(e)}\n")

        if show_progress:
            print_progress_bar(i + 1, total, description="Analyzing audio files")

# Main function
def main():
    """Parse command-line arguments and execute the appropriate subcommand.
    Notes:
        - Defines three subcommands: check, cover-art, and info.
        - Uses argparse to handle command-line input.
    """
    parser = argparse.ArgumentParser(description="Audio file utilities")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run", required=True)

    # Define 'check' subcommand
    check_parser = subparsers.add_parser("check", help="Check integrity of audio files")
    check_parser.add_argument("path", type=path_type, help="Path to the file or directory to check")
    check_parser.add_argument("--verbose", action="store_true", help="Print results to console, no progress bar")
    check_parser.add_argument("--save-log", action="store_true", help="Save log file when verbose")

    # Define 'cover-art' subcommand
    cover_art_parser = subparsers.add_parser("cover-art", help="Hide or show cover art files")
    cover_art_group = cover_art_parser.add_mutually_exclusive_group(required=True)
    cover_art_group.add_argument("--hide", action="store_true", help="Hide cover art files")
    cover_art_group.add_argument("--show", action="store_true", help="Show cover art files")
    cover_art_parser.add_argument("path", type=directory_path, help="Path to the directory to process")

    # Define 'info' subcommand
    info_parser = subparsers.add_parser("info", help="Get information about audio files")
    info_parser.add_argument("path", type=path_type, help="Path to the file or directory to analyze")
    info_parser.add_argument("-o", "--output", default="audio_analysis.txt", help="Output file name")
    info_parser.add_argument("--verbose", action="store_true", help="Print results to console, no progress bar")

    args = parser.parse_args()  # Parse the command-line arguments

    if args.command == "check":
        check_integrity(args.path, verbose=args.verbose, save_log=args.save_log)
    elif args.command == "cover-art":
        process_cover_art(args.path, hide=args.hide)
    elif args.command == "info":
        if args.verbose:
            analyze_audio(args.path, sys.stdout, show_progress=False)  # Verbose: console output, no progress
        else:
            output_file = args.output
            if output_file == "audio_analysis.txt":
                output_file = f"audio_analysis_{datetime.datetime.now().strftime('%Y%m%d')}.txt"  # Timestamp default
            with open(output_file, "w") as f:
                analyze_audio(args.path, f, show_progress=True)  # File output with progress
            print(f"Analysis complete. Results saved to {output_file}")

if __name__ == "__main__":
    main()  # Entry point of the script
