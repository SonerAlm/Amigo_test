import os                                                                                                                                            
  import requests
  from dotenv import load_dotenv                                                                                                                       
   
  load_dotenv()                                                                                                                                        

  SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
  FROM_EMAIL = os.getenv("FROM_EMAIL")
  REPORT_EMAIL = os.getenv("REPORT_EMAIL", "")                                                                                                         
   
  def send_report():                                                                                                                                   
      report_path = os.path.join(os.path.dirname(__file__), ".tmp", "email_body.html")
                                                                                                                                                       
      with open(report_path, "r") as f:
          html_content = f.read()                                                                                                                      

      recipients = [{"email": r.strip()} for r in REPORT_EMAIL.split(",") if r.strip()]                                                                
   
      response = requests.post(                                                                                                                        
          "https://api.sendgrid.com/v3/mail/send",
          headers={
              "Authorization": f"Bearer {SENDGRID_API_KEY}",
              "Content-Type": "application/json"                                                                                                       
          },
          json={                                                                                                                                       
              "personalizations": [{"to": recipients}],
              "from": {"email": FROM_EMAIL},
              "subject": "Amigo eSIM Daily Performance Report",
              "content": [{"type": "text/html", "value": html_content}]                                                                                
          }
      )                                                                                                                                                

      if response.status_code == 202:                                                                                                                  
          print("Email sent successfully via SendGrid")
      else:                                                                                                                                            
          raise Exception(f"SendGrid error {response.status_code}: {response.text}")

  if __name__ == "__main__":                                                                                                                           
      send_report()
