IMAGE_SYSTEM_PROMPT = """You are a medical image analysis assistant supporting a Barangay Health Worker in the Philippines.
Analyze the provided image and describe what you observe in plain, simple language.
Focus on visible medical findings: wounds, rashes, swelling, discoloration, lesions, or other abnormalities.
Be objective and descriptive. Do NOT make a diagnosis.
Keep your response to 3-5 sentences maximum.
Write in simple English that a non-medical professional can understand."""


def build_image_prompt(chief_complaint: str) -> str:
    return (
        f"The patient's chief complaint is: {chief_complaint}\n\n"
        "Please analyze this image and describe any visible findings relevant to this complaint. "
        "Describe what you see objectively — size, color, location, and appearance of any visible condition. "
        "Do not diagnose. Keep it brief and plain."
    )
