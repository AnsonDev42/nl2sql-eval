import streamlit as st
import pandas as pd
import boto3
import os
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

from PIL import Image
from io import BytesIO
from utils import extract_images_from_eml
import glob
import awswrangler as wr
from utils import about_page, parse_image_filename, extract_images_page
# Set page config
st.set_page_config(
    page_title="NL2SQL Evaluation Tool",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Define constants
CSV_PATH = "nl2sql_wide_experiment_data_20250306_203950.csv"
WORKING_CSV_PATH = "nl2sql_wide_experiment_data_working_copy.csv"
IMAGES_DIR = "images"
load_dotenv()  # take environment variables

# Define evaluation fields
EVAL_FIELDS = {
    "Correctness": {"options": [0, 1], "help": "1 if SQL is syntactically and logically correct, 0 otherwise"},
    "ResultMatch": {"options": [0, 1], "help": "1 if output matches expectations, 0 otherwise"},
    "UserRating": {"options": list(range(1, 6)), "help": "Subjective rating on SQL quality (1-5)"},
    "VoiceUsed": {"options": [0], "help": "Mark 0 for all rows"},
    "ChartRating": {"options": list(range(1, 6)), "help": "Rating on generated chart quality (1-5)"},
    "AnalystChartChoice": {"options": ["bar", "line", "pie", "scatter", "table", "other"], "help": "Preferred chart type"}
}

# Function to create a working copy of the CSV file
def create_working_copy():
    if not os.path.exists(WORKING_CSV_PATH):
        df = pd.read_csv(CSV_PATH)
        df.to_csv(WORKING_CSV_PATH, index=False)
        st.success("Created working copy of the CSV file.")
    return pd.read_csv(WORKING_CSV_PATH)

# Function to save the working copy
def save_working_copy(df):
    df.to_csv(WORKING_CSV_PATH, index=False)
    st.success("Saved changes to working copy.")
    
# Function to finalize changes to original CSV
def finalize_changes():
    working_df = pd.read_csv(WORKING_CSV_PATH)
    working_df.to_csv(CSV_PATH, index=False)
    st.success("Changes saved to original CSV file.")
    

# Function to execute SQL query using AWS Glue
@st.cache_data
def execute_sql(sql_query, database):
    try:
        wr.config.logging_level = 0
        session = boto3.Session(region_name="eu-west-1")

        results = wr.athena.read_sql_query(
            sql=sql_query,
            database=os.getenv("athena_database"),
            boto3_session=session,
        )
        return results
    except Exception as e:
        print(f"Error executing SQL query: {e}")
        st.error(f"Error executing SQL query: {e}")
        return None

# Function to generate a chart based on data and chart type
def generate_chart(data, chart_type):
    if data is None or data.empty:
        return None
    
    try:
        if chart_type == "bar":
            fig = px.bar(data)
        elif chart_type == "line":
            fig = px.line(data)
        elif chart_type == "pie":
            # Use first string column as names and first numeric as values
            string_cols = data.select_dtypes(include=['object']).columns
            numeric_cols = data.select_dtypes(include=['number']).columns
            
            if len(string_cols) > 0 and len(numeric_cols) > 0:
                fig = px.pie(data, names=string_cols[0], values=numeric_cols[0])
            else:
                fig = px.pie(data)
        elif chart_type == "scatter":
            numeric_cols = data.select_dtypes(include=['number']).columns
            if len(numeric_cols) >= 2:
                fig = px.scatter(data, x=numeric_cols[0], y=numeric_cols[1])
            else:
                fig = px.scatter(data)
        elif chart_type == "table":
            fig = go.Figure(data=[go.Table(
                header=dict(values=list(data.columns),
                            fill_color='paleturquoise',
                            align='left'),
                cells=dict(values=[data[col] for col in data.columns],
                          fill_color='lavender',
                          align='left'))
            ])
        else:
            fig = px.bar(data)  # Default to bar chart
            
        return fig
    except Exception as e:
        st.error(f"Error generating chart: {e}")
        return None

# Function to find chart images for a specific question and model
def find_chart_images(question_id, model_name):
    # Check if images directory exists
    if not os.path.exists(IMAGES_DIR):
        return []
    
    # Format the model name to match the image file naming pattern
    # Remove "_NoRAG" or "_RAG" from model name, as it's separate in the filename
    model_pattern = model_name.replace("_NoRAG", "").replace("_RAG", "")
    
    # Determine if this is RAG or NoRAG
    rag_type = "RAG" if "_RAG" in model_name else "NoRAG"
    
    # Search pattern for both specific and generic cases
    search_pattern = os.path.join(IMAGES_DIR, f"chart_Q{question_id}_{model_pattern}-{rag_type}.png")
    
    # Find matching files
    matching_files = glob.glob(search_pattern)
    
    return matching_files

# Function to display chart images for a question and model
def display_chart_images(question_id, model_name):
    chart_images = find_chart_images(question_id, model_name)
    
    if not chart_images:
        st.info(f"No chart images found for Question {question_id} with model {model_name}")
        return
    
    st.subheader("Chart Images")
    
    for image_path in chart_images:
        try:
            img = Image.open(image_path)
            caption = os.path.basename(image_path)
            st.image(img, caption=caption, width=500)
            
            # Add download button
            # with open(image_path, "rb") as file:
            #     btn = st.download_button(
            #         label=f"Download {caption}",
            #         data=file,
            #         file_name=caption
            #     )
        except Exception as e:
            st.error(f"Error displaying image {image_path}: {e}")

# Function to list all available chart images
def list_all_chart_images():
    if not os.path.exists(IMAGES_DIR):
        return []
    
    pattern = os.path.join(IMAGES_DIR, "chart_*.png")
    return glob.glob(pattern)



# Main app
def main():
    st.title("NL2SQL Evaluation Tool")
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Evaluation", "Extract Images", "Chart Gallery", "About"])
    
    if page == "Evaluation":
        evaluation_page()
    elif page == "Extract Images":
        extract_images_page()
    elif page == "Chart Gallery":
        chart_gallery_page()
    else:
        about_page()

# Evaluation page
def evaluation_page():
    st.header("SQL Evaluation")
    
    # Load data
    df = create_working_copy()
    
    # Get list of models from column names
    model_columns = [col for col in df.columns if '_SQL' in col]
    models = [col.split('_SQL')[0] for col in model_columns]
    
    # Select question
    question_id = st.selectbox("Select Question ID", df['QuestionID'].unique())
    
    if question_id:
                # Select model
        model = st.selectbox("Select Model", models)
        question_data = df[df['QuestionID'] == question_id].iloc[0]
        
        st.subheader("Question")
        st.write(question_data['QueryText'])
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Domain:** {question_data['Domain']}")
        with col2:
            st.write(f"**Complexity:** {question_data['Complexity']}")

        col_gold, col_model = st.columns(2)
        with col_gold:
            st.subheader("Gold SQL")
            st.code(question_data['GoldSQL'], language="sql")
        if model:
            # Get model columns
            model_sql_col = f"{model}_SQL"
            model_correctness_col = f"{model}_Correctness"
            model_resultmatch_col = f"{model}_ResultMatch"
            model_userrating_col = f"{model}_UserRating"
            model_voiceused_col = f"{model}_VoiceUsed"
            model_chartrating_col = f"{model}_ChartRating"
            model_chartchoice_col = f"{model}_AnalystChartChoice"
            
            # Display model SQL
            with col_model:
                st.subheader(f"{model} SQL")
                model_sql = question_data[model_sql_col]
                st.code(model_sql, language="sql")
            
            # AWS Glue SQL execution
            st.subheader("SQL Execution")
            # change this col layout to row layout
            col3, col4 = st.columns(2)
            with col3:
                database = "edw_prod"
                # database = st.text_input("AWS Glue Database Name")
                results = execute_sql(question_data['GoldSQL'], database)
                if results is not None:
                    st.write("Gold SQL Results:")
                    st.dataframe(results)
            with col4:
                results = execute_sql(model_sql, database)
                if results is not None:
                    st.write(f"{model} SQL Results:")
                    st.dataframe(results)
            
            # Evaluation section
            st.subheader("Evaluation")
            
            with st.form("evaluation_form"):
                # Correctness
                correctness = st.radio(
                    "Correctness (0 or 1)",
                    EVAL_FIELDS["Correctness"]["options"],
                    help=EVAL_FIELDS["Correctness"]["help"],
                    index=EVAL_FIELDS["Correctness"]["options"].index(int(question_data[model_correctness_col])) if pd.notna(question_data[model_correctness_col]) else 0
                )
                
                # ResultMatch
                resultmatch = st.radio(
                    "Result Match (0 or 1)",
                    EVAL_FIELDS["ResultMatch"]["options"],
                    help=EVAL_FIELDS["ResultMatch"]["help"],
                    index=EVAL_FIELDS["ResultMatch"]["options"].index(int(question_data[model_resultmatch_col])) if pd.notna(question_data[model_resultmatch_col]) else 0
                )
                
                # UserRating
                userrating = st.select_slider(
                    "User Rating (1-5)",
                    EVAL_FIELDS["UserRating"]["options"],
                    help=EVAL_FIELDS["UserRating"]["help"],
                    value=int(question_data[model_userrating_col]) if pd.notna(question_data[model_userrating_col]) else 3
                )
                
                # VoiceUsed (always 0)
                voiceused = 0
                
                # Chart visualization
                st.subheader("Chart Visualization")
                available_chart_types = EVAL_FIELDS["AnalystChartChoice"]["options"]
                selected_chart_type = st.selectbox(
                    "Select Chart Type",
                    available_chart_types,
                    index=available_chart_types.index(question_data[model_chartchoice_col]) if pd.notna(question_data[model_chartchoice_col]) and question_data[model_chartchoice_col] in available_chart_types else 0
                )
                
                # Chart rating
                chartrating = st.select_slider(
                    "Chart Rating (1-5)",
                    EVAL_FIELDS["ChartRating"]["options"],
                    help=EVAL_FIELDS["ChartRating"]["help"],
                    value=int(question_data[model_chartrating_col]) if pd.notna(question_data[model_chartrating_col]) else 3
                )
                
                # Submit button
                submitted = st.form_submit_button("Save Evaluation")
                
                if submitted:
                    # Update dataframe with evaluation
                    df.loc[df['QuestionID'] == question_id, model_correctness_col] = correctness
                    df.loc[df['QuestionID'] == question_id, model_resultmatch_col] = resultmatch
                    df.loc[df['QuestionID'] == question_id, model_userrating_col] = userrating
                    df.loc[df['QuestionID'] == question_id, model_voiceused_col] = voiceused
                    df.loc[df['QuestionID'] == question_id, model_chartrating_col] = chartrating
                    df.loc[df['QuestionID'] == question_id, model_chartchoice_col] = selected_chart_type
                    
                    # Save working copy
                    save_working_copy(df)
            
            # Chart preview (if data is available)
            if database:
                try:
                    # Use either gold or model SQL based on toggle
                    use_gold = st.checkbox("Use Gold SQL for chart preview", value=True)
                    sql_to_use = question_data['GoldSQL'] if use_gold else model_sql
                    
                    # Execute query for chart
                    chart_data = execute_sql(sql_to_use, database)
                    
                    if chart_data is not None and not chart_data.empty:
                        # Generate chart
                        fig = generate_chart(chart_data, selected_chart_type)
                        if fig:
                            st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Error generating chart preview: {e}")
               # Display chart images for this question and model
    # Save final changes
    if st.button("Save all changes to original CSV", type="primary"):
        finalize_changes()
    display_chart_images(question_id, model) 



# Chart Gallery page
def chart_gallery_page():
    st.header("Chart Image Gallery")
    
    # Get all chart images
    chart_images = list_all_chart_images()
    
    if not chart_images:
        st.warning("No chart images found in the images directory.")
        return
    
    # Filtering options
    st.subheader("Filter Images")
    
    # Parse all image filenames to extract metadata
    image_metadata = []
    for img_path in chart_images:
        metadata = parse_image_filename(os.path.basename(img_path))
        if metadata:
            metadata["path"] = img_path
            image_metadata.append(metadata)
    
    # Create dataframe for filtering
    if image_metadata:
        img_df = pd.DataFrame(image_metadata)
        
        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            selected_question_id = st.multiselect(
                "Filter by Question ID",
                options=sorted(img_df["question_id"].unique()),
                default=[]
            )
        
        with col2:
            selected_models = st.multiselect(
                "Filter by Model",
                options=sorted(img_df["model_name"].unique()),
                default=[]
            )
        
        # Apply filters
        filtered_df = img_df
        if selected_question_id:
            filtered_df = filtered_df[filtered_df["question_id"].isin(selected_question_id)]
        if selected_models:
            filtered_df = filtered_df[filtered_df["model_name"].isin(selected_models)]
        
        # Display filtered images
        if not filtered_df.empty:
            st.subheader(f"Showing {len(filtered_df)} Charts")
            
            # Display images in a grid
            cols = st.columns(2)  # 2 columns for displaying images
            
            for i, (_, row) in enumerate(filtered_df.iterrows()):
                col_idx = i % 2
                with cols[col_idx]:
                    try:
                        img = Image.open(row["path"])
                        st.image(
                            img, 
                            caption=f"Q{row['question_id']} - {row['model_name']}",
                            use_column_width=True
                        )
                        
                    except Exception as e:
                        st.error(f"Error displaying image: {e}")
        else:
            st.info("No images match the selected filters.")
    else:
        st.warning("Could not parse image filenames correctly.")

# About page

if __name__ == "__main__":
    main()