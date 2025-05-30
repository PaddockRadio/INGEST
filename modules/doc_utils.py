import os
import logging
from modules.sanitation_utils import clean_text

def convert_documents_to_text(folder):
    try:
        for file in os.listdir(folder):
            path = os.path.join(folder, file)
            text = ""
            if file.endswith(".docx"):
                from docx import Document
                doc = Document(path)
                text = "\n".join([p.text for p in doc.paragraphs])
            elif file.endswith(".pdf"):
                import fitz
                doc = fitz.open(path)
                text = "\n".join([page.get_text() for page in doc])
            elif file.endswith(".txt"):
                with open(path, "r") as f:
                    text = f.read()
            if text.strip():
                with open(os.path.join(folder, "publish.txt"), "w") as f:
                    f.write(clean_text(text.strip()))
                break
    except Exception as e:
        logging.warning(f"Document conversion failed: {e}")
