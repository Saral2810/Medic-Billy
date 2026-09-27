## 🧠 ML Pipeline

```mermaid
flowchart LR
    A["📄 Bill Image / PDF"] --> B["🖼️ Page Extraction"]
    B --> C["⚙️ Image Preprocessing"]
    C --> D["👁️ Vision Understanding"]
    D --> E["🤖 Qwen3-VL 4B"]
    E --> F["📦 Structured JSON"]
    F --> G["🛡️ Pydantic Validation"]
    G --> H["✅ Standard Bill JSON"]

    E -. "Fine-tuned with<br/>QLoRA / LoRA" .-> I["🎯 Domain Adaptation"]
    I -.-> E

    G -->|Invalid / Unreadable| J["⚠️ Human Review"]

    classDef input fill:#0f172a,stroke:#38bdf8,color:#fff,stroke-width:2px
    classDef process fill:#172554,stroke:#60a5fa,color:#fff,stroke-width:2px
    classDef model fill:#312e81,stroke:#a78bfa,color:#fff,stroke-width:3px
    classDef output fill:#064e3b,stroke:#34d399,color:#fff,stroke-width:2px
    classDef warning fill:#451a03,stroke:#f59e0b,color:#fff,stroke-width:2px

    class A input
    class B,C,D,F,G process
    class E,I model
    class H output
    class J warning
