from google import genai
import  logfire

logfire_token='pylf_v1_us_9KZvzp4mxc3FST1MRFK6NJs7LtH6yZYYwdw4BXKq6Kyq'
client = genai.Client(api_key="AIzaSyAVYfSmN_Eq00TQycVi143pEkYpDeYtwrw")
logfire.configure(token=logfire_token)

response = client.models.generate_content(
    model="gemini-2.0-flash", contents="Explain how AI works in a few words"
)
logfire.info(response.text)
print(response.text)
