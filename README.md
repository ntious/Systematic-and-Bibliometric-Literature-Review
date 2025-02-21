# Systematic and Bibliometric Literature Review Workshop
A systematic literature review is a structured approach to synthesizing research, enabling researchers to draw comprehensive conclusions from existing studies. A bibliometric literature review, on the other hand, uses statistical and computational methods to analyze research output and trends, providing insights into research impacts and scholarly networks.
Given the increased emphasis on evidence-based research in academia, postgraduate students and early carrer researchers must master these methodologies early in their studies. Currently, many postgraduate students and early carrer researchers globally struggle with these techniques, often resulting in suboptimal reviews that limit the quality of their research. 
This repository contains materials, scripts, and resources for the **Workshop on Systematic and Bibliometric Literature Review**, organized at **I. K. NTI**. The workshop aims to train postgraduate students in conducting high-quality literature reviews using **systematic review protocols and bibliometric analysis tools**.


## Learning Objectives
By the end of this workshop, participants will:
- Develop a **systematic review protocol**, including clear research questions, inclusion/exclusion criteria, and search strategies.
- Utilize **bibliometric tools** (VOSviewer, R for bibliometrics) to identify key research trends, authors, and journals.
- Apply **text mining and NLP techniques** to analyze academic literature.
- Identify **research gaps and propose future research directions**.
- Integrate systematic and bibliometric review methodologies into their research projects.

## Repository Structure
```
systematic-review-workshop/
│── docs/                             
│             
│   ├── syllabus.pdf                    # Detailed syllabus (if applicable)
│   ├── learning_outcomes.md            # Workshop learning outcomes
│   ├── resources.md                    # Additional reading and links
│
│── slides/                             # Presentation slides
│   ├── day1_introduction.pdf
│   ├── day2_tools.pdf
│   ├── day3_application.pdf
│
│── scripts/                            # Code and scripts for bibliometric analysis
│   ├── literature_search.py            # Automated literature search script
│   ├── prisma_diagram.py               # Script for generating PRISMA diagrams
│   ├── text_mining.ipynb               # NLP & text mining for systematic reviews
│   ├── bibliometric_analysis.R         # R script for bibliometric study
│
│── data/                               # Sample datasets for hands-on practice
│   ├── research_papers.csv             # Sample metadata for bibliometric analysis
│   ├── reference_library.bib           # BibTeX file with reference collection
│
│── examples/                           # Examples of systematic/bibliometric reviews
│   ├── sample_systematic_review.pdf    # Example systematic literature review
│   ├── sample_bibliometric_review.pdf  # Example bibliometric literature review
│
│── .gitignore                          # Ignore unnecessary files (cache, outputs)
│── README.md                           # Main project documentation
│── LICENSE                             # Open-source license (MIT, Apache, etc.)
│── CONTRIBUTING.md                     # Guidelines for contributors
│── requirements.txt                     # Python dependencies for scripts
```

## Getting Started
### **Prerequisites**
Ensure you have the following installed:
- **Python 3.8+** (for literature search and NLP)
- **R and RStudio** (for bibliometric analysis)
- **Mendeley or Zotero** (for reference management)
- **VOSviewer** (for network visualization)

### **Installation**
To install required Python dependencies:
pip install -r requirements.txt

### **Running the Scripts**
1. Automated Literature Search
python scripts/literature_search.py
2. Generate PRISMA Flow Diagram
python scripts/prisma_diagram.py
3. Perform Text Mining & NLP
jupyter notebook scripts/text_mining.ipynb

### **Contribution Guidelines**
We welcome contributions! Please follow these steps:

### Fork the repository.
- Create a new branch (feature-branch).
- Commit changes with a clear message.
- Submit a pull request for review.

### License
This repository is licensed under the MIT License – see the LICENSE file for details.

### Contact
- For inquiries or collaborations, please contact: Dr. Nti
📧 ntious1@gmail.com
📍 University of Cincinnati, USA
