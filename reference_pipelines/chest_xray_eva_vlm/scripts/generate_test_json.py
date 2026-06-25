import json
from pathlib import Path


def generate_qa_samples():
    base_dir = Path("test_images")
    output_file = "qa_test_samples.json"

    samples = []

    # NORMAL cases
    normal_dir = base_dir / "normal"
    if normal_dir.exists():
        for img_path in normal_dir.glob("*"):
            samples.append(
                {
                    "image_path": str(img_path),
                    "question": "Does this patient have pneumonia?",
                    "ground_truth": "No, the lungs are clear. There is no evidence of pneumonia, consolidation, or effusion.",
                    "context": "The chest X-ray shows clear lung fields without any focal airspace opacities, pleural effusions, or pneumothorax.",
                }
            )

    # PNEUMONIA cases
    pneumonia_dir = base_dir / "pneumonia"
    if pneumonia_dir.exists():
        for img_path in pneumonia_dir.glob("*"):
            samples.append(
                {
                    "image_path": str(img_path),
                    "question": "What findings suggest an abnormality in this image?",
                    "ground_truth": "The image shows focal opacification or consolidation, which is characteristic of pneumonia.",
                    "context": "Focal airspace opacities are visible, suggesting consolidation consistent with a diagnosis of pneumonia.",
                }
            )

    with open(output_file, "w") as f:
        json.dump(samples, f, indent=2)

    print(f"Generated {len(samples)} QA samples in {output_file}")


if __name__ == "__main__":
    generate_qa_samples()
