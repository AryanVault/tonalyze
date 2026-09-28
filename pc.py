import cv2
import numpy as np
import pandas as pd
import streamlit as st

# Global variable to store the clicked RGB value
clicked_rgb = None

def load_dataset(csv_path):
    """Load the skin tone dataset."""
    dataset = pd.read_csv(csv_path)
    return dataset

def calculate_euclidean_distance(color1, color2):
    """Calculate the Euclidean distance between two RGB colors."""
    return np.sqrt(np.sum((np.array(color1) - np.array(color2))**2))

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

def click_event(event, x, y, flags, param):
    """Mouse click event to capture the RGB value of the clicked pixel."""
    global clicked_rgb
    image = param
    if event == cv2.EVENT_LBUTTONDOWN:
        # Capture the RGB color of the clicked pixel
        bgr_color = image[y, x]
        clicked_rgb = [int(bgr_color[2]), int(bgr_color[1]), int(bgr_color[0])]  # Convert BGR to RGB
        st.write(f"Clicked RGB: {clicked_rgb}")

def draw_color_swatches(clicked_rgb, closest_match):
    """Draw the clicked color and the recommended color swatches on an image."""
    # Create a black canvas to draw the color swatches
    canvas = np.zeros((800, 800, 3), dtype=np.uint8)
    

    # Draw the clicked skin tone color swatch
    cv2.rectangle(canvas, (50, 50), (200, 150), (clicked_rgb[2], clicked_rgb[1], clicked_rgb[0]), -1)
    cv2.putText(canvas, "Clicked Skin Tone", (50, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    # Draw the recommended colors swatches
    colors = [
        ("Warm", closest_match['Recommended Colors (Warm)']),
        ("Bright", closest_match['Recommended Colors (Bright)']),
        ("Dark", closest_match['Recommended Colors (Dark)']),
        ("Pastel", closest_match['Recommended Colors (Pastel)']),
        ("Metallic", closest_match['Recommended Colors (Metallic)'])
    ]

    y_offset = 200  # Starting y position for the recommended colors swatches

    for color_type, color_list in colors:
        cv2.putText(canvas, f"{color_type} Colors", (50, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        y_offset += 30

        # Display each color as a swatch
        color_names = color_list.split(',')  # Assuming colors are separated by commas
        for i, color_name in enumerate(color_names):
            # Extract the color code
            color_code = color_name.split('(')[-1].split(')')[0].strip()  # Get the hex code without brackets
            
            if len(color_code) == 7:  # Ensure the hex code is valid
                r, g, b = [int(color_code[i:i+2], 16) for i in (1, 3, 5)]  # Convert hex to RGB
                cv2.rectangle(canvas, (50 + i * 120, y_offset), (160 + i * 120, y_offset + 40), (b, g, r), -1)
                cv2.putText(canvas, color_name.strip(), (50 + i * 120, y_offset + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
        y_offset += 80

    return canvas

# Streamlit app
def main():
    st.title("Skin Tone Color Recommender")
    st.write("Upload an image and click on a skin pixel to get color recommendations.")

    # Upload the CSV file
    csv_file = "colors.csv"
    dataset = load_dataset(csv_file)

    # Upload the image
    uploaded_file = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        # Read the uploaded file as a NumPy array
        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        st.image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), caption="Uploaded Image", use_container_width=True)

        # Wait for a click to capture skin tone
        if st.button("Click to Detect Skin Tone"):
            cv2.imshow("Select Skin Pixel", image)
            cv2.setMouseCallback("Select Skin Pixel", click_event, param=image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

            if clicked_rgb is not None:
                # Find the closest skin tone
                closest_match = find_closest_skin_tone(clicked_rgb, dataset)
                st.write("Closest Match:")
                st.write(f"Skin Tone Name: {closest_match['Skin Tone Name']}")
                st.write(f"Closest RGB Value: [{closest_match['Red']}, {closest_match['Green']}, {closest_match['Blue']}]")
                st.write(f"Recommended Colors: {closest_match[['Recommended Colors (Warm)', 'Recommended Colors (Bright)', 'Recommended Colors (Dark)', 'Recommended Colors (Pastel)', 'Recommended Colors (Metallic)']].to_dict()}")

                # Display color swatches
                color_swatches = draw_color_swatches(clicked_rgb, closest_match)
                st.image(cv2.cvtColor(color_swatches, cv2.COLOR_BGR2RGB), caption="Color Swatches", use_container_width=True)

if __name__ == "__main__":
    main()