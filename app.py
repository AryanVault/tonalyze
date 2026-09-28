import streamlit as st
import numpy as np
import pandas as pd
from PIL import Image
import cv2

# Function to load dataset
def load_dataset(csv_path):
    """Load the skin tone dataset."""
    dataset = pd.read_csv(csv_path)
    return dataset

# Function to calculate Euclidean distance between two colors
def calculate_euclidean_distance(color1, color2):
    """Calculate the Euclidean distance between two RGB colors."""
    return np.sqrt(np.sum((np.array(color1) - np.array(color2))**2))

# Function to find the closest skin tone
def find_closest_skin_tone(avg_color, dataset):
    """Find the closest skin tone and recommended colors."""
    distances = []
    for i, row in dataset.iterrows():
        skin_rgb = [row['Red'], row['Green'], row['Blue']]
        distance = calculate_euclidean_distance(avg_color, skin_rgb)
        distances.append(distance)
    
    dataset['distance'] = distances
    closest_match = dataset.loc[dataset['distance'].idxmin()]
    return closest_match

# Function to display color swatches
def display_color_swatches(colors):
    """Display color swatches along with their name and hex code."""
    swatch_columns = st.columns(len(colors))
    for i, color in enumerate(colors):
        with swatch_columns[i]:
            # Extract color name and hex code (e.g., "Light Brown (#D2B49A)")
            color_name, hex_code = color.split('(')
            hex_code = hex_code.strip(')').strip()  # Remove any trailing ')' and spaces

            # Ensure the hex code is valid (starts with "#" and has 6 characters)
            if hex_code.startswith('#') and len(hex_code) == 7:
                # Draw the color swatch
                st.markdown(
                    f'<div style="background-color:{hex_code}; width: 50px; height: 50px; border-radius: 5px;"></div>',
                    unsafe_allow_html=True,
                )
                st.write(f"{color_name.strip()} ({hex_code})")

def main():
    st.title("Skin Tone Color Recommender")
    st.write("Upload an image and click or move the slider to detect the skin tone.")

    # Upload the CSV file for skin tone dataset
    csv_file = "colors.csv"
    dataset = load_dataset(csv_file)

    # Upload the image
    uploaded_file = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        # Load the image using Pillow
        img = Image.open(uploaded_file)
        img_array = np.array(img)

        # Display the image in Streamlit
        st.image(img, caption="Uploaded Image", use_container_width=True)

        # Add sliders for X and Y coordinates to simulate a crosshair
        st.sidebar.subheader("Move the Crosshair")
        x = st.sidebar.slider("X-coordinate", 0, img.size[0] - 1, img.size[0] // 2)
        y = st.sidebar.slider("Y-coordinate", 0, img.size[1] - 1, img.size[1] // 2)

        # Visualize the crosshair over the image using a red dot or line
        img_with_crosshair = img_array.copy()

        # Draw a red crosshair on the image at the selected coordinates
        cv2.drawMarker(img_with_crosshair, (x, y), (0, 0, 255), markerType=cv2.MARKER_CROSS, markerSize=20, thickness=2)

        # Show the image with the crosshair in Streamlit
        st.image(img_with_crosshair, caption="Image with Crosshair", use_container_width=True)

        # Get the RGB value of the selected pixel
        clicked_rgb = img_array[y, x][:3]

        # Display the RGB value of the selected pixel
        st.write(f"Selected Pixel RGB: {clicked_rgb}")

        # Display the clicked pixel color as a swatch
        hex_code = f"#{clicked_rgb[0]:02x}{clicked_rgb[1]:02x}{clicked_rgb[2]:02x}".upper()
        st.subheader("Clicked Pixel Color")
        st.markdown(
            f'<div style="background-color:{hex_code}; width: 100px; height: 100px; border-radius: 5px;"></div>',
            unsafe_allow_html=True,
        )
        st.write(f"Hex Code: {hex_code}")
        st.write(f"RGB: {clicked_rgb}")

        # Find the closest matching skin tone from the dataset
        closest_match = find_closest_skin_tone(clicked_rgb, dataset)
        st.write("Closest Match:")
        st.write(f"Skin Tone Name: {closest_match['Skin Tone Name']}")
        st.write(f"Closest RGB Value: [{closest_match['Red']}, {closest_match['Green']}, {closest_match['Blue']}]")

        # Display recommended color swatches for each category
        st.subheader("Recommended Colors")
        
        categories = [
            ("Warm", closest_match['Recommended Colors (Warm)']),
            ("Bright", closest_match['Recommended Colors (Bright)']),
            ("Dark", closest_match['Recommended Colors (Dark)']),
            ("Pastel", closest_match['Recommended Colors (Pastel)']),
            ("Metallic", closest_match['Recommended Colors (Metallic)']),
        ]

        for category_name, color_list in categories:
            st.write(f"**{category_name} Colors**")
            color_names = color_list.split(',')  # Assuming colors are separated by commas
            display_color_swatches(color_names)

if __name__ == "__main__":
    main()
