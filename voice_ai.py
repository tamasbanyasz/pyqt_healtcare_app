'''
https://realpython.com/python-speech-recognition/https://realpython.com/python-speech-recognition/


'''


import speech_recognition as sr


class VoiceSearch:
    def __init__(self):
        self.recognizer = sr.Recognizer()

    def voice_command(self):
        
        with sr.Microphone() as source:
            print("Say a name: ")
            audio = self.recognizer.listen(source)
        
        try:
            # Voice recognize by Google Speech API 
            command = self.recognizer.recognize_google(audio, language="en-US")
            print(f"Recognized name: {command}")
            return command
        except sr.UnknownValueError:
            print("Dont understand.")
            return None
        except sr.RequestError as e:
            print(f"Error: {e}")
            return None

    def search_name_in_dataframe(self, name, original_data):
        
        if name:
            filtered_data = original_data[original_data['Name'].str.contains(name, case=False, na=False)]
            
            if filtered_data.empty:
                print("Name doesn't exxist, back to original datas.")
                return original_data
            else:
                print(f"Founded records: \n{filtered_data}")
                return filtered_data
        else:
            print("Didn't happen search, back to original datas.")
            return original_data
