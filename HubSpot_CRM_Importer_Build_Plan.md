# HubSpot CRM Importer
## Nine-step build plan

Use one synthetic business-card photo as the main test fixture. Finish each step’s verification before starting the next. Use the HubSpot test account for all CRM operations.

| Step | Build | Done when |
| --- | --- | --- |
| 1. Upload a photo | Serve a plain react typescript page from FastAPI. Send a photo to a Python endpoint and display the response. | The browser shows the uploaded filename and size. |
| 2. Show sample contact fields | Return a fixed sample contact from Python with name, email, phone, and job title. Display those fields on the page. | Uploading the photo shows the sample contact in the browser. |
| 3. Extract with OpenAI | Replace the fixed response with structured extraction from the photo. Leave absent or unreadable fields blank and keep source evidence for review. | A clear card yields the expected fields. An unreadable email is left blank. |
| 4. Look up a test contact | Connect to the HubSpot test account from Python. Validate the email and look up a matching contact. | A seeded email returns its contact ID. A new email returns no match. |
| 5. Save a clear case | Create a contact when there is no match. Fill blank fields on a match and hold conflicts for review. | The first upload creates a contact. A repeat returns the same ID. A matching contact’s blank phone field can be filled. |
| 6. Download the PDF | Generate a PDF summary from the same result shown on the page. Include the HubSpot status and a record link when confirmed. | You can download a summary for a confirmed test contact and open the CRM record from it. |
| 7. Resolve an exception | Show the field that needs attention. Let the user correct, confirm, or skip the proposed change, then validate again before saving. | A blurry email or conflicting title pauses the write. After a confirmed save, the refreshed PDF reflects the result. |
| 8. Recover from an interrupted save | Persist import status and the contact ID in SQLite. Check HubSpot before retrying an uncertain write. | Refreshing recovers the result. A simulated timeout after creation still leaves one contact. |
| 9. Accept PDFs | Add text-based PDF input, then scanned PDF input. Pass both through the same validation and save rules as photos. | Both input types produce the expected contact result and downloadable summary. |

### First session

Build `GET /` for the upload page and `POST /uploads` for the file. Submit one local photo and verify its filename and size appear in the browser.
