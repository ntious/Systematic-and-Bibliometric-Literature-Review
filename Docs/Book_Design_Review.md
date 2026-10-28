# Book-informed design review

Reviewed: 2026-10-23. Status: proposed design improvements, not approved requirements or implemented features.

## Source and coverage

User-supplied file: `systematic-approaches-to-a-successful-literature-review-3e.pdf`, titled *Systematic Approaches to a Successful Literature Review*, by Andrew Booth, Anthea Sutton, Mark Clowes and Marrissa Martyn-St James. Source identifier in the PDF: DOI `10.4135/9781036232009`.

The supplied PDF has 113 pages: front matter, an introductory chapter and references. Its contents list the later methodological chapters, but those chapters are not included in this file. Page references below are PDF positions, not the printed textbook pagination. Export metadata says 2026 while the internal copyright page says 2022; retain that discrepancy until bibliographic details are verified. No claim is made to have reviewed the full book.

Local extracted text remains under ignored `outputs/book-design-review/`. The source PDF has not been copied into the repository. These notes paraphrase ideas briefly and distinguish them from original application proposals. Bibliography entries are leads for further reading, not evidence that their cited works have been read.

## Findings and application implications

| Available material | Application proposal | Relationship to current design |
| --- | --- | --- |
| Purpose, audience and available evidence shape review choices (PDF 15, 51–52). | Add a structured review brief: intended decision, audience, deadline, expertise and evidence type. Use it with the question when suggesting methods. | Extends question-intent matching; domain keywords alone remain insufficient. |
| Different review families serve different purposes (PDF 31–47). | Use a small set of explicit review profiles, each with suitable workflow defaults, conduct references and reporting guidance. Keep profile choice editable and approved. | Review-type selection is planned; the current catalogue does not encode complete review profiles. |
| SALSA distinguishes search, appraisal, synthesis and analysis (PDF 19–24, 33). | Offer a simple progress overview with these dimensions while retaining our detailed stages and approval history. | Improves navigation; does not replace the eleven-stage workflow. |
| Protocols protect scope and communicate methods (PDF 34). | Display planned versus actually executed methods and deviations, rather than treating protocol text as proof of execution. | Reinforces version binding, amendments and the methods-report safeguards. |
| Review methods depend on the form of available data (PDF 52). | Recommend at planning time, then reassess feasibility after extraction. Link each failed prerequisite to the fields or judgments needed. | Strengthens the provisional catalogue; field-name declarations are not actual data validation. |
| Mixed-method reviews integrate qualitative and quantitative strands in different ways (PDF 44–46). | Model separate linked questions/strands, synthesis outputs and an approved integration step. Consider joint displays with links to evidence from each strand. | New candidate design; two charts side by side are not automatically a mixed-method synthesis. |
| Literature can include reports, policy documents, theses and books (PDF 51–52). | Store source genre separately from file format and retrieval provider; apply appropriate intake, extraction and appraisal guidance. | Extends PDF/reference intake beyond journal-paper assumptions without promising unsupported parsers. |
| Conduct manuals, reporting guidance and quality assessment have distinct purposes (PDF 34–35, 53–54). | Type knowledge-base sources and relations accordingly; avoid suggesting that a reporting checklist validates a statistical method. | Important refinement to the initial source-linked graph before expert curation. |
| Common weaknesses include unsupported claims, isolated study summaries and overgeneralisation (PDF 49–50). | Add advisory checks for evidence-linked statements, question coverage, contradictory findings, missing data and meaningful grouping. Human review resolves warnings; software cannot certify truth. | Extends the evidence approval and traceable-reporting approach. |
| Learning features include summaries, exercises, explanations and guidance (PDF 18–26). | Add short contextual explanations, original worked examples and synthetic practice exercises. Keep help accessible without AI. | Supports educational adoption without reproducing the book's exercises or tables. |
| Existing reviews may support an update or another suitable product (PDF 40–41, 48). | Add an early existing-review check and an explicit new-review/update/overview decision. Overviews need primary-study overlap tracking. | Future profile feature; do not combine reviews as if they were independent primary studies. |
| Audience affects communication and purpose (PDF 51). | Offer audience-specific draft summaries using the same frozen approved findings, with separate human approval. | Extends reporting; wording can change, but supporting evidence and uncertainty must remain consistent. |

## Priority recommendations

1. First add the review brief and typed methodological-source roles to the knowledge-base design. These directly improve recommendation inputs and provenance.
2. Connect method requirements to actual approved extraction snapshots, with versioned researcher decisions.
3. Build a question-to-evidence-to-analysis-to-claim coverage view and contextual input guidance.
4. Develop mixed-method strands and integration after the basic approval and execution architecture is reliable.

Do not automatically import every textbook method into an executable catalogue. Methods mentioned only in the contents require their underlying guidance to be read and curated. Workload heuristics should not become universal numerical defaults. Rapid-review shortcuts need explicit rationale and approval. Review-profile selection must not advertise methodological conformity that the software does not enforce.

The separate 20–30 review-paper exercise remains useful for evaluating recommendations; the textbook informs the architecture rather than replacing that evaluation.
