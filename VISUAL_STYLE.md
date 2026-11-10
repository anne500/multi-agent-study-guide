# 🎨 Shared Architecture Diagram Style

This standard is shared by the five AI learning project repositories.
Use explicit Mermaid class definitions so colors do not depend on the viewer's theme.

| Role | Color | Fill | Border | Text |
| --- | --- | --- | --- | --- |
| Input, processing, retrieval, deterministic tools | 🔵 Blue | `#DBEAFE` | `#2563EB` | `#172554` |
| Model calls and model context | 🟣 Purple | `#EDE9FE` | `#7C3AED` | `#3B0764` |
| Persistent data, files, indexes, memory | 🟦 Teal | `#CCFBF1` | `#0F766E` | `#134E4A` |
| Decisions, conditional gates, uncertain states | 🟡 Amber | `#FEF3C7` | `#B45309` | `#78350F` |
| Human approval or manual review | 🟠 Orange | `#FFEDD5` | `#C2410C` | `#7C2D12` |
| Outputs, completion, explicit passing outcomes | 🟢 Green | `#DCFCE7` | `#15803D` | `#14532D` |
| Errors, failed checks, rejected outcomes | 🔴 Red | `#FEE2E2` | `#B91C1C` | `#7F1D1D` |
| Neutral boundaries and baseline states | ⚪ Slate | `#F8FAFC` | `#475569` | `#0F172A` |

## Rules

- Apply this palette to README architecture diagrams and supporting workflow diagrams.
- Assign colors by component role, not by project or diagram position.
- Keep labels and shapes meaningful; never rely on color alone.
- Green identifies an output or explicit pass, not a guarantee that generated content is correct.
- Teal identifies storage even when the stored content is model-generated.
- Keep measurement charts' series and outcome legends separate from architecture roles.
- Use top-down layouts for larger workflows and avoid overly wide diagrams.
- Add a matching text explanation and link verification evidence where relevant.

## Reusable Mermaid classes

```text
classDef default fill:#F8FAFC,stroke:#475569,color:#0F172A,stroke-width:2px;
classDef process fill:#DBEAFE,stroke:#2563EB,color:#172554,stroke-width:2px;
classDef model fill:#EDE9FE,stroke:#7C3AED,color:#3B0764,stroke-width:2px;
classDef store fill:#CCFBF1,stroke:#0F766E,color:#134E4A,stroke-width:2px;
classDef decision fill:#FEF3C7,stroke:#B45309,color:#78350F,stroke-width:2px;
classDef human fill:#FFEDD5,stroke:#C2410C,color:#7C2D12,stroke-width:2px;
classDef output fill:#DCFCE7,stroke:#15803D,color:#14532D,stroke-width:2px;
classDef failure fill:#FEE2E2,stroke:#B91C1C,color:#7F1D1D,stroke-width:2px;
```

Apply classes with assignments such as `class ModelNode model;` and
`class DatabaseNode store;`. Unassigned nodes use the neutral default.

The learning roadmap uses its own documented learning/research categories;
architecture colors describe component roles.

## README presentation standard

- Begin with a project-specific title icon and a colored overview graphic.
- Use the same section icons: 🧩 architecture, ✨ features, 🧰 requirements,
  🚀 setup, ⚙️ configuration, 💬 examples, 🧪 verification,
  📊 results, 🗂️ evidence, 💾 storage, ⚠️ limitations,
  🧭 roadmap, 🟪 research, and 📚 attribution.
- Add compact navigation with stable section anchors.
- Use meaningful diagrams, result graphics, and comparison tables throughout.
- Preserve examples, evidence boundaries, and limitations when improving presentation.
- Label pass, fail, planned, and unverified states in text as well as color.
- Keep technical code blocks copyable and free from decorative edits.

## Tutorial provenance standard

Each project README must visibly acknowledge the related tutorial author and publisher, link the exact tutorial title, and distinguish the original learning foundation from repository-specific adaptations, experiments, and research connections. For this learning sequence, credit Darsh Shah and freeCodeCamp in the introductory callout and the Tutorial Acknowledgment and Attribution section.
