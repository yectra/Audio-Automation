# Importing necessary modules
import os  # Operating system module
import tempfile  # Temporary files/directories module
import aiofiles  # Asynchronous file operations module

# Importing from FastAPI framework
from fastapi import FastAPI, UploadFile, File, HTTPException, Form  # FastAPI classes and functions
from fastapi.responses import FileResponse  # File response class

# Importing from pydub library for audio manipulation
from pydub import AudioSegment # Audio manipulation classes

import mutagen  # Audio metadata module
import moviepy.editor as mp  # Video editing module
from gtts import gTTS  # Text-to-speech conversion class

# Create FastAPI app instance
app = FastAPI()

# Get system temporary directory
temp_dir = tempfile.gettempdir()

async def process_uploaded_file(file: UploadFile) -> str:
    """Process the uploaded file and save it to a temporary directory."""
    try:
        temp_file_path = os.path.join(temp_dir, file.filename)
        async with aiofiles.open(temp_file_path, "wb") as buffer:
            await buffer.write(await file.read())
        return temp_file_path
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    
@app.post("/audio-format-conversion/")
async def audio_format_conversion(
    file: UploadFile = File(...),
    output_format: str = Form(...)):
    """Endpoint to convert an audio file to a different format."""
    temp_file_path = None
    output_file_path = None
    try:
        temp_file_path = await process_uploaded_file(file)
        audio = AudioSegment.from_file(temp_file_path)

        output_format = output_format.lower()
        if output_format not in ['ac3',  'au', 'caf',  'flac', 'mp2', 'mp3', 'voc', 'wav']:
            raise HTTPException(status_code=400, detail="Invalid output format")

        output_file_path = os.path.join(temp_dir, f"converted_audio.{output_format}")
        audio.export(output_file_path, format=output_format)

        return FileResponse(output_file_path, media_type=f"audio/{output_format}", filename=f"converted_audio.{output_format}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting audio format: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.post("/audio-part-segmentation/")
async def audio_segmentation(
    file: UploadFile = File(...),
    start_time: str = Form(None),
    end_time: str = Form(None),
    output_format: str = Form(None)):
    """Endpoint to segment an audio file based on start and end times."""
    temp_file_path = None
    output_file_path = None
    try:
        temp_file_path = await process_uploaded_file(file)
        audio = AudioSegment.from_file(temp_file_path)

        if not output_format:
            output_format = file.filename.split('.')[-1]

        start_time_ms = convert_to_milliseconds(start_time) if start_time else 0
        end_time_ms = convert_to_milliseconds(end_time) if end_time else len(audio)

        if start_time_ms < 0 or start_time_ms >= len(audio):
            raise HTTPException(status_code=400, detail="Invalid start time")
        if end_time_ms <= start_time_ms or end_time_ms > len(audio):
            raise HTTPException(status_code=400, detail="Invalid end time")

        cut_segment = audio[start_time_ms:end_time_ms]

        output_file_path = os.path.join(temp_dir, f"output_cut_audio.{output_format}")
        cut_segment.export(output_file_path, format=output_format)

        return FileResponse(output_file_path, media_type=f"audio/{output_format}", filename=f"output_cut_audio.{output_format}")

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.post("/adjust-playback-speed/")
async def playback_speed(
    file: UploadFile = File(...),
    speed_factor: float = Form(...),
    output_format: str = Form(...)):

    temp_file_path = None
    output_file_path = None
    try:
        # Process the uploaded file and convert it to AudioSegment
        temp_file_path = await process_uploaded_file(file)
        audio = AudioSegment.from_file(temp_file_path)

        if speed_factor <= 0:
            raise HTTPException(status_code=400, detail="Speed factor must be greater than zero")

        # Adjust the playback speed
        new_audio = audio._spawn(audio.raw_data, overrides={
            "frame_rate": int(audio.frame_rate * speed_factor)
        }).set_frame_rate(audio.frame_rate)

        # Save the modified audio to a file
        output_file_path = os.path.join(temp_dir, f"output_speed_audio.{output_format}")
        new_audio.export(output_file_path, format=output_format)

        return FileResponse(output_file_path, media_type=f"audio/{output_format}", filename=f"output_speed_audio.{output_format}")

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error changing audio playback speed: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.post("/adjust-volume/")
async def adjust_volume(
    file: UploadFile = File(...),
    volume_change_db: float = Form(...),  # Volume change in decibels
    output_format: str = Form(None),
):
    temp_file_path = None
    output_file_path = None
    try:
        # Process the uploaded file and convert it to AudioSegment
        temp_file_path = await process_uploaded_file(file)
        audio = AudioSegment.from_file(temp_file_path)

        # Convert decibels to linear gain
        linear_gain = 10 ** (volume_change_db / 20.0)

        # Adjust the volume using the linear gain
        adjusted_audio = audio.apply_gain(linear_gain)

        # Save the adjusted audio to a file
        output_file_path = os.path.join(temp_dir, f"adjusted_audio.{output_format}")
        adjusted_audio.export(output_file_path, format=output_format)

        return FileResponse(output_file_path, media_type=f"audio/{output_format}", filename=f"adjusted_audio.{output_format}")

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adjusting volume: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        
@app.post("/reverse-audio/")
async def reverse_audio(
    file: UploadFile = File(...),
    output_format: str = Form(None),
):
    temp_file_path = None
    output_file_path = None
    try:
        # Process the uploaded file and convert it to AudioSegment
        temp_file_path = await process_uploaded_file(file)
        audio = AudioSegment.from_file(temp_file_path)

        # Reverse the audio
        reversed_audio = audio.reverse()

        if not output_format:
            output_format = file.filename.split('.')[-1]

        # Save the reversed audio to a file
        output_file_path = os.path.join(temp_dir, f"reversed_audio.{output_format}")
        reversed_audio.export(output_file_path, format=output_format)

        return FileResponse(output_file_path, media_type=f"audio/{output_format}", filename=f"reversed_audio.{output_format}")

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reversing audio: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.post("/audio-features/")
async def audio_features(
    file: UploadFile = File(...)
):
    temp_file_path = None
    try:
        # Process the uploaded file and convert it to AudioSegment
        temp_file_path = await process_uploaded_file(file)
        audio = AudioSegment.from_file(temp_file_path)

        # Get audio features
        duration_ms = len(audio)
        channels = audio.channels
        sample_width = audio.sample_width
        frame_rate = audio.frame_rate
        max_possible_amplitude = audio.max_possible_amplitude

        # Get metadata using mutagen
        audio_file = mutagen.File(temp_file_path)
        if audio_file is not None:
            metadata = {
                "title": audio_file.get("title", ["Unknown"])[0],
                "artist": audio_file.get("artist", ["Unknown"])[0],
                "album": audio_file.get("album", ["Unknown"])[0],
                "genre": audio_file.get("genre", ["Unknown"])[0],
                "year": audio_file.get("date", ["Unknown"])[0],
            }
        else:
            metadata = {
                "title": "Unknown",
                "artist": "Unknown",
                "album": "Unknown",
                "genre": "Unknown",
                "year": "Unknown",
            }

        features = {
            "duration_ms": duration_ms,
            "duration_seconds": duration_ms / 1000,
            "channels": channels,
            "sample_width": sample_width,
            "frame_rate": frame_rate,
            "max_possible_amplitude": max_possible_amplitude,
            "metadata": metadata
        }

        return features

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting audio features: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@app.post("/merge-audios/")
async def merge_audios(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    output_format: str = Form(...)
):
    temp_file_path1 = None
    temp_file_path2 = None
    output_file_path = None
    try:
        # Process the uploaded files and convert them to AudioSegments
        temp_file_path1 = await process_uploaded_file(file1)
        temp_file_path2 = await process_uploaded_file(file2)
        audio1 = AudioSegment.from_file(temp_file_path1)
        audio2 = AudioSegment.from_file(temp_file_path2)

        # Overlay audio2 on audio1
        merged_audio = audio1.overlay(audio2)

        # Save the merged audio to a file
        output_file_path = os.path.join(temp_dir, f"merged_audio.{output_format}")
        merged_audio.export(output_file_path, format=output_format)

        return FileResponse(output_file_path, media_type=f"audio/{output_format}", filename=f"merged_audio.{output_format}")

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error merging audios: {str(e)}")
    finally:
        if temp_file_path1 and os.path.exists(temp_file_path1):
            os.remove(temp_file_path1)
        if temp_file_path2 and os.path.exists(temp_file_path2):
            os.remove(temp_file_path2)

@app.post("/concatenate-audios/")
async def concatenate_audio(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    output_format: str = Form(...),):

    temp_file_path1 = None
    temp_file_path2 = None
    output_file_path = None
    try:
        # Process the uploaded files and convert them to AudioSegments
        temp_file_path1 = await process_uploaded_file(file1)
        temp_file_path2 = await process_uploaded_file(file2)
        audio1 = AudioSegment.from_file(temp_file_path1)
        audio2 = AudioSegment.from_file(temp_file_path2)

        concatenated_audio = audio1 + audio2

        output_file_path = tempfile.mktemp(suffix=f".{output_format}")
        concatenated_audio.export(output_file_path, format=output_format)
        
        return FileResponse(output_file_path, media_type=f"audio/{output_format}", filename=f"concatenated_audio.{output_format}")

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error concatenating audios: {str(e)}")
    finally:
        if temp_file_path1 and os.path.exists(temp_file_path1):
            os.remove(temp_file_path1)
        if temp_file_path2 and os.path.exists(temp_file_path2):
            os.remove(temp_file_path2)

@app.post("/echo-effects/")
async def echo_effect(
    file: UploadFile = File(...),
    delay_time: float = Form(...),  # Delay time in seconds
    loop_count: int = Form(1),  # Number of times to loop the echo effect
    output_format: str = Form(None)):
    temp_file_path = None
    output_file_path = None
    try:
        # Process the uploaded file and convert it to AudioSegment
        temp_file_path = await process_uploaded_file(file)
        audio = AudioSegment.from_file(temp_file_path)

        # Apply the echo effect
        echo_audio = audio
        for _ in range(loop_count):
            echo_audio = echo_audio.overlay(audio, position=(len(echo_audio) + (delay_time * 1000)))

        # Save the audio with echo effect to a file
        output_file_path = os.path.join(temp_dir, f"echo_audio.{output_format}")
        echo_audio.export(output_file_path, format=output_format)

        return FileResponse(output_file_path, media_type=f"audio/{output_format}", filename=f"echo_audio.{output_format}")

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error applying echo effect: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.post("/fadein-out-effects/")
async def fadein_out_effect(
    file: UploadFile = File(...),
    apply_fade_in: bool = Form(False),
    fade_in_duration: float = Form(0),  # Fade in duration in milliseconds
    apply_fade_out: bool = Form(False),
    fade_out_duration: float = Form(0),  # Fade out duration in milliseconds
    output_format: str = Form(None),):
    temp_file_path = None
    output_file_path = None
    try:
        # Process the uploaded file and convert it to AudioSegment
        temp_file_path = await process_uploaded_file(file)
        audio = AudioSegment.from_file(temp_file_path)

        # Apply fade in and fade out effects
        faded_audio = audio
        if apply_fade_in:
            faded_audio = faded_audio.fade_in(int(fade_in_duration))
        if apply_fade_out:
            faded_audio = faded_audio.fade_out(int(fade_out_duration))

        if not output_format:
            output_format = file.filename.split('.')[-1]

        # Save the faded audio to a file
        output_file_path = os.path.join(temp_dir, f"faded_audio.{output_format}")
        faded_audio.export(output_file_path, format=output_format)

        return FileResponse(output_file_path, media_type=f"audio/{output_format}", filename=f"faded_audio.{output_format}")
       
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error applying fade in and fade out effect: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        
@app.post("/video-to-audio/")
async def video_to_audio(
    file: UploadFile = File(...),
    output_format: str = Form(...)):

    temp_file_path = None
    output_file_path = None
    try:
        # Process the uploaded file
        temp_file_path = await process_uploaded_file(file)

        # Convert video to audio
        video = mp.VideoFileClip(temp_file_path)
        audio = video.audio

        # Save the audio to a file
        output_file_path = os.path.join(temp_dir, f"converted_audio.{output_format}")
        audio.write_audiofile(output_file_path)

        return FileResponse(output_file_path, media_type=f"audio/{output_format}", filename=f"converted_audio.{output_format}")

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting video to audio: {str(e)}")
    finally:
        # Close the video and audio objects
        video.reader.close()
        audio.close()
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        
@app.post("/text-to-audio/")
async def text_to_audio(
    text: str = Form(...),
    language: str = Form("en"),
    output_format: str = Form("mp3"),
):
    output_file_path = None
    try:
        # Convert text to speech
        tts = gTTS(text=text, lang=language, slow=False)

        # Save the audio to a file
        output_file_path = os.path.join(temp_dir, f"voice_audio.{output_format}")
        tts.save(output_file_path)

        return FileResponse(output_file_path, media_type=f"audio/{output_format}", filename=f"voice_audio.{output_format}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting text to audio: {str(e)}")
  
def pitch_shift(audio: AudioSegment, octaves: float) -> AudioSegment:
    """Shift the pitch of the audio by a number of octaves."""
    new_sample_rate = int(audio.frame_rate * (2.0 ** octaves))
    return audio._spawn(audio.raw_data, overrides={'frame_rate': new_sample_rate}).set_frame_rate(audio.frame_rate)

def convert_to_milliseconds(time_str: str) -> int:
    """Convert a time string in the format HH:MM:SS or MM:SS or SS to milliseconds."""
    if not time_str:
        return None
    time_parts = time_str.split(":")
    if len(time_parts) == 1:
        return int(time_parts[0]) * 1000
    elif len(time_parts) == 2:
        return int(time_parts[0]) * 60 * 1000 + int(time_parts[1]) * 1000
    elif len(time_parts) == 3:
        return int(time_parts[0]) * 60 * 60 * 1000 + int(time_parts[1]) * 60 * 1000 + int(time_parts[2]) * 1000
    else:
        raise HTTPException(status_code=400, detail="Invalid time format")  