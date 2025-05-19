import google.generativeai as genai

genai.configure(api_key="AIzaSyBVqsIwR4LvrggeWkDty8v-2iy6eU-tz1A")
models = genai.list_models()

for model in models:
    print(model.name)
