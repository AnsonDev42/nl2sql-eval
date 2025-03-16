import streamlit as st
import email
import mimetypes
import os
import datetime
from PIL import Image
import re
def extract_images_from_eml():
    try:
        # Create images directory if it doesn't exist
        os.makedirs('images', exist_ok=True)
        
        # Read the EML file
        with open("Assistance Sought for a Paper I'm Working on --Request for Human Evaluation of NL2SQL Model Performance.eml", 'rb') as f:
            msg = email.message_from_binary_file(f)
        
        # Extract attachments
        image_paths = []
        for part in msg.walk():
            if part.get_content_maintype() == 'image':
                # Get filename if available, otherwise generate one
                filename = part.get_filename()
                if not filename:
                    ext = mimetypes.guess_extension(part.get_content_type())
                    if not ext:
                        ext = '.bin'
                    filename = f'image-{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}{ext}'
                
                # Save to file
                filepath = os.path.join('images', filename)
                with open(filepath, 'wb') as f:
                    f.write(part.get_payload(decode=True))
                
                image_paths.append(filepath)
                
        return image_paths
    except Exception as e:
        st.error(f"Error extracting images: {e}")
        return []

def about_page():
    st.header("About NL2SQL Evaluation Tool")
    
    st.write("""
    This tool is designed to help evaluate text-to-SQL conversions by comparing gold standard SQL queries with 
    LLM-generated SQL queries. It allows you to:
    
    1. View and compare gold and generated SQL queries
    2. Execute queries against AWS Glue tables to view results
    3. Evaluate SQL correctness, result match, user rating, chart quality, and preferred chart type
    4. Extract and view images from the attached EML file
    5. Save evaluation results to the CSV file
    
    ### Evaluation Guidelines
    
    - **Correctness (0 or 1)**: Mark 1 if SQL is syntactically and logically correct, 0 otherwise
    - **ResultMatch (0 or 1)**: Mark 1 if outputs match expectations, 0 otherwise
    - **UserRating (1-5)**: Subjective rating on SQL quality
    - **VoiceUsed (0)**: Always mark 0
    - **ChartRating (1-5)**: Rate how well the generated chart represents the data
    - **AnalystChartChoice**: Indicate preferred chart type
    """)


# Function to parse image filename to extract question ID and model info
def parse_image_filename(filename):
    # Extract info from filename using regex pattern
    pattern = r"chart_Q(\d+)_(.+)-(NoRAG|RAG)\.png"
    match = re.search(pattern, filename)
    
    if match:
        question_id = int(match.group(1))
        model_name = match.group(2)
        rag_type = match.group(3)
        
        # Reconstruct model name as it appears in the CSV
        full_model_name = f"{model_name}_{rag_type}"
        
        return {
            "question_id": question_id,
            "model_name": full_model_name,
            "rag_type": rag_type,
            "filename": os.path.basename(filename)
        }
    return None

    # Extract images page
def extract_images_page():
    st.header("Extract Images from EML")
    
    if st.button("Extract Images"):
        image_paths = extract_images_from_eml()
        
        if image_paths:
            st.success(f"Successfully extracted {len(image_paths)} images.")
            
            # Display the images
            st.subheader("Extracted Images")
            
            for i, path in enumerate(image_paths):
                try:
                    img = Image.open(path)
                    st.image(img, caption=f"Image {i+1}: {os.path.basename(path)}")
                    
                    # Add download button
                    with open(path, "rb") as file:
                        btn = st.download_button(
                            label=f"Download {os.path.basename(path)}",
                            data=file,
                            file_name=os.path.basename(path)
                        )
                except Exception as e:
                    st.error(f"Error displaying image {i+1}: {e}")
        else:
            st.warning("No images found or extraction failed.")
