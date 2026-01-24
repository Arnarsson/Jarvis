# Domain Pitfalls: Personal AI Assistant with Screen Recall

**Domain:** Personal AI assistant / screen recall / RAG memory / workflow automation
**Project:** Jarvis - AI Chief of Staff
**Researched:** 2026-01-24
**Confidence:** HIGH (verified via multiple sources including official docs, security research, and real-world post-mortems)

---

## Critical Pitfalls

Mistakes that cause rewrites, security breaches, or project failure.

---

### Pitfall 1: The Microsoft Recall Privacy Trap

**What goes wrong:** Building screenshot capture without encryption, sensitive data filtering, or proper access controls - creating a searchable database of everything including passwords, credit cards, and private messages.

**Why it happens:** Focus on functionality over security. "Get it working first, secure it later" mentality. Microsoft's initial Recall implementation stored screenshots in an unencrypted SQLite database with no redaction of sensitive data.

**Consequences:**
- Security researchers demonstrated extraction of all user activity with simple tools (TotalRecall by Alexander Hagenah)
- Data persisted even after deletion from source apps (emails, messages)
- No exclusion of private browsing in Chrome (only Edge InPrivate was excluded)
- Regulatory intervention (UK ICO inquiry)
- Complete feature postponement and 6-month security overhaul

**Prevention:**
1. **Encryption from day one:** All screenshots encrypted at rest using keys tied to biometric authentication (TPM + Windows Hello ESS pattern)
2. **VBS Enclave pattern:** Process sensitive data in isolated security enclave, not main application memory
3. **Sensitive content filtering:** Build regex patterns for credit cards, passwords, API keys BEFORE storing any screenshots
4. **Opt-in only:** Never enable by default; require explicit user consent with clear explanation
5. **Application exclusions:** Allow users to blacklist apps (password managers, banking apps, private browsing)

**Detection (warning signs):**
- Screenshots stored as plain files in accessible location
- Database queryable without authentication
- No audit log of who accessed screenshot data
- Sensitive data visible in stored screenshots during testing

**Phase mapping:** Must be addressed in Phase 1 (core capture infrastructure). Cannot be retrofitted.

**Sources:**
- [Microsoft Recall security analysis - DoublePulsar](https://doublepulsar.com/microsoft-recall-on-copilot-pc-testing-the-security-and-privacy-implications-ddb296093b6c)
- [Microsoft's security update blog](https://blogs.windows.com/windowsexperience/2024/09/27/update-on-recall-security-and-privacy-architecture/)
- [TechTarget on Recall privacy risks](https://www.techtarget.com/searchenterpriseai/feature/Privacy-and-security-risks-surrounding-Microsoft-Recall)

---

### Pitfall 2: MCP Server as Attack Vector

**What goes wrong:** MCP servers become the highest-value target in the system - compromising one server grants access to all connected service tokens (Gmail, Drive, Calendar), enabling cross-service attacks.

**Why it happens:** MCP protocol designed for functionality over security. No built-in authentication requirements, session IDs in URLs, no message signing. Teams trust third-party MCP servers without security audits.

**Consequences:**
- **Token theft:** Attacker breaches MCP server, gains all OAuth tokens
- **Prompt injection:** Malicious tool descriptions inject hidden commands into AI context
- **Tool poisoning:** Weather-checking tool secretly exfiltrates private conversations
- **Confused deputy:** Server grants same access to all users, no user-context enforcement
- **Sampling attacks:** Resource theft draining AI compute quotas, conversation hijacking

**Prevention:**
1. **Never use third-party MCP servers** for sensitive integrations - build your own
2. **Strict input validation:** Filter all inputs for dangerous patterns before reaching LLM
3. **Token isolation:** Each integration gets isolated token storage, not shared credentials
4. **Human-in-the-loop mandatory:** Treat MCP spec's "SHOULD always be human in loop" as MUST
5. **Cryptographic server verification:** Clients verify server identity before sending sensitive data
6. **Session ID security:** Never expose session IDs in URLs or logs
7. **Rate limiting:** Prevent resource theft through sampling abuse

**Detection (warning signs):**
- MCP servers accepting connections without authentication
- Tool descriptions not reviewed for hidden instructions
- Session tokens shared across multiple integrations
- No audit log of MCP tool invocations

**Phase mapping:** Must be designed into MCP architecture from start. Phase 2 (integrations) cannot proceed without security foundation from Phase 1.

**Sources:**
- [Red Hat: MCP security risks and controls](https://www.redhat.com/en/blog/model-context-protocol-mcp-understanding-security-risks-and-controls)
- [Palo Alto Unit 42: MCP attack vectors](https://unit42.paloaltonetworks.com/model-context-protocol-attack-vectors/)
- [Microsoft: Plug, Play, and Prey](https://techcommunity.microsoft.com/blog/microsoftdefendercloudblog/plug-play-and-prey-the-security-risks-of-the-model-context-protocol/4410829)
- [MCP Official Security Best Practices](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices)

---

### Pitfall 3: RAG Retrieval Quality Collapse at Scale

**What goes wrong:** System retrieves wrong documents, outdated information, or misses relevant context entirely - leading to hallucinated or incorrect AI responses that users trust.

**Why it happens:** Naive RAG implementations use pure vector similarity without metadata, timestamps, or hybrid search. Works for demos, fails under real-world demands.

**Consequences:**
- **Low precision:** Retrieved chunks don't match query intent
- **Low recall:** Relevant documents missed entirely
- **Outdated responses:** AI confidently provides stale information
- **Hallucination cascade:** Model generates from retrieved garbage
- **User trust erosion:** Wrong answers destroy confidence in entire system

**Prevention:**
1. **Hybrid search mandatory:** Combine semantic vectors with BM25 keyword search, metadata filtering, recency signals
2. **Timestamp everything:** Data freshness pipeline to mark, update, or archive outdated documents
3. **Metadata-aware retrieval:** Filter by type, source, date BEFORE semantic ranking
4. **Chunking strategy:** Test multiple chunk sizes; 512-1536 tokens typical, but domain-dependent
5. **Evaluation framework:** Don't rely on BLEU/ROUGE - build domain-specific retrieval evaluation with known-good queries
6. **Ingestion quality:** Failure at ingestion is root cause of most hallucinations - validate data quality before indexing

**Detection (warning signs):**
- Retrieval returning documents that "feel wrong" for the query
- Same answer for very different questions
- No way to explain WHY a document was retrieved
- RAG outputs contradicting known facts

**Phase mapping:** RAG architecture decisions in Phase 2 (memory system). Plan for iteration - initial implementation will need tuning.

**Sources:**
- [Seven Failure Points in RAG Systems (arXiv)](https://arxiv.org/html/2401.05856v1)
- [23 RAG Pitfalls and How to Fix Them](https://www.nb-data.com/p/23-rag-pitfalls-and-how-to-fix-them)
- [InfoWorld: How to build RAG at scale](https://www.infoworld.com/article/4108159/how-to-build-rag-at-scale.html)

---

### Pitfall 4: Automation Trust Collapse (False Positive Tax)

**What goes wrong:** Automation executes wrong actions, or flags too many false positives, destroying user trust. Once trust is lost, users disable automation entirely.

**Why it happens:** Optimizing for "catching everything" instead of precision. No gradual trust-building mechanism. Destructive actions without confirmation.

**Consequences:**
- **False positive flood:** 72% of security teams report false positives damage productivity (Finite State survey)
- **Real threat blindness:** 33% of companies late responding to actual issues because investigating false positives (VikingCloud)
- **User workarounds:** IT teams develop workarounds that bypass automation entirely
- **Credibility death spiral:** Executives stop believing system assessments

**Prevention:**
1. **Tiered trust model:** Start with "suggest only", graduate to "auto-execute" based on track record
2. **Precision over recall:** Better to miss some opportunities than execute wrong actions
3. **Destructive action blocks:** Never auto-execute deletions, payments, or irreversible actions
4. **Human approval for high-stakes:** Financial transactions, public communications require explicit approval
5. **Undo capability:** Every automated action must be reversible for at least 24 hours
6. **Trust metrics:** Track false positive rate per automation type; suspend automation above threshold

**Detection (warning signs):**
- Users saying "I just ignore those notifications"
- Automation suggestions consistently wrong
- Users manually doing tasks automation should handle
- No feedback loop on automation accuracy

**Phase mapping:** Trust model architecture in Phase 1 (core design). Automation features in Phase 3+.

**Sources:**
- [Netcraft: The False Positive Tax](https://www.netcraft.com/blog/the-false-positive-tax-how-bad-automation-destroys-security-program-credibility/)
- [Invicti: False Positives in Application Security](https://www.invicti.com/white-papers/false-positives-in-application-security-whitepaper)
- [Frontegg: AI Agent Governance](https://frontegg.com/blog/ai-agent-governance-starts-with-guardrails)

---

### Pitfall 5: Desktop Agent Resource Starvation

**What goes wrong:** Screen capture and OCR consume so much CPU/memory that user's main work suffers. System becomes unusable during capture or processing.

**Why it happens:** Continuous high-frequency capture. Synchronous OCR blocking main thread. No resource limits. LLM inference competing for RAM.

**Consequences:**
- Desktop becomes sluggish, fans spin up constantly
- Users disable the agent
- System swap kills performance (35 tokens/sec drops to 1.5 tokens/sec)
- Battery drain on laptops

**Prevention:**
1. **Adaptive capture frequency:** Capture when screen changes, not on fixed interval (event-driven)
2. **Async processing pipeline:** Capture in one thread, OCR in another, never block UI
3. **Resource budgets:** Hard limits on CPU% and memory usage; throttle when exceeded
4. **Local vs server processing decision:** Heavy OCR/LLM on server, lightweight capture on desktop
5. **VRAM-aware scheduling:** If using local LLM, ensure model fits in VRAM without swap
6. **Idle-first processing:** Process screenshots when system is idle, not during active use

**Detection (warning signs):**
- CPU consistently above 30% from agent processes
- Memory usage growing unbounded over time
- System swapping to disk
- Users reporting "computer feels slow"

**Phase mapping:** Desktop agent architecture in Phase 1. Non-negotiable constraint for Jarvis.

**Sources:**
- [LocalLLM: Ollama VRAM Requirements](https://localllm.in/blog/ollama-vram-requirements-for-local-llms)
- [The 2026 Local LLM Hardware Guide](https://medium.com/@jameshugo598/the-2026-local-llm-hardware-guide-surviving-the-ram-crisis-fa67e8c95804)
- [RAM Requirements for Local LLMs](https://apxml.com/courses/getting-started-local-llms/chapter-2-preparing-local-environment/hardware-ram)

---

## Moderate Pitfalls

Mistakes that cause delays, technical debt, or degraded user experience.

---

### Pitfall 6: Vector Storage Cost Explosion

**What goes wrong:** What starts as a prototype with thousands of embeddings balloons into terabytes of storage costing hundreds/month.

**Why it happens:** Not planning for scale. Using full float32 embeddings. No cleanup of old/duplicate data. Re-indexing when embedding models change.

**Consequences:**
- 100GB raw text becomes ~3.17 TB logical storage (31.7x increase)
- Budget shock when prototype goes to production
- Slow index builds and query performance
- Full re-index required when changing embedding models

**Prevention:**
1. **Quantization from start:** INT8 quantization cuts memory 75% with minimal recall impact; binary quantization can reduce costs 99%
2. **Dimension budget:** 512-1536 dimensions is sweet spot; higher dimensions rarely justify cost
3. **Serverless vector DB:** Separate storage and compute for independent scaling
4. **Data lifecycle:** Archive or delete old embeddings; don't keep everything forever
5. **Embedding model lock-in awareness:** Changing models requires full re-index; choose carefully

**Detection (warning signs):**
- Vector storage growing faster than document count
- Query latency increasing over time
- Storage costs doubling monthly

**Phase mapping:** Vector database decisions in Phase 2 (memory system). Plan capacity from start.

**Sources:**
- [Pure Storage: Managing Vector Storage Bloat](https://blog.purestorage.com/purely-technical/managing-vector-storage-bloat-insights-for-scalable-systems/)
- [Vector Embeddings at Scale (Medium)](https://medium.com/@singhrajni/vector-embeddings-at-scale-a-complete-guide-to-cutting-storage-costs-by-90-a39cb631f856)
- [DagsHub: Common Pitfalls with Vector Databases](https://dagshub.com/blog/common-pitfalls-to-avoid-when-using-vector-databases/)

---

### Pitfall 7: OCR Accuracy Cliff

**What goes wrong:** OCR works great in testing, fails on real screenshots with varied fonts, UI elements, low contrast, or non-standard layouts.

**Why it happens:** Testing only on clean images. Using Tesseract without preprocessing. Not handling screen-specific content (icons, buttons, mixed layouts).

**Consequences:**
- Garbled text in RAG database
- Search misses relevant content
- User frustration with "I know I saw that but can't find it"

**Prevention:**
1. **Don't rely solely on Tesseract:** Cloud OCR (Google Vision, AWS Textract) achieves 98%+ accuracy vs Tesseract's struggles with complex layouts
2. **Screen-optimized preprocessing:** High DPI capture (300+), noise reduction, contrast enhancement
3. **Hybrid approach:** Use local OCR for basic text, cloud for complex layouts (cost vs accuracy tradeoff)
4. **Test on real screenshots:** Include dark mode, small fonts, non-Latin characters, code, tables
5. **Confidence thresholds:** Mark low-confidence OCR output; don't pollute RAG with garbage

**Detection (warning signs):**
- OCR output contains obvious errors visible to human reviewer
- Search returning wrong results for text clearly visible in screenshots
- Specific applications consistently produce garbage OCR

**Phase mapping:** OCR implementation in Phase 1 (capture pipeline). Requires iteration.

**Sources:**
- [OCR Benchmark 2026 - AIMultiple](https://research.aimultiple.com/ocr-accuracy/)
- [Klippa: Best Tesseract Alternatives 2026](https://www.klippa.com/en/blog/information/the-best-alternative-to-tesseract/)
- [Eklavvya: Google Vision vs EasyOCR vs Tesseract](https://www.eklavvya.com/blog/best-ocr-answersheet-evaluation/)

---

### Pitfall 8: Google API Quota Hell

**What goes wrong:** Hit rate limits during normal usage, blocking critical integrations. OAuth consent screen problems. Unexpected billing.

**Why it happens:** Not understanding quota tiers. Testing with personal account, deploying with different limits. Not implementing exponential backoff.

**Consequences:**
- "Error 403: rate_limit_exceeded" for users
- Integration failures at peak usage times
- Unexpected cloud bills from quota overages

**Prevention:**
1. **Understand quota structure:** New user authorization rate limits, per-minute limits, per-user limits
2. **Request quota increases early:** Some APIs have low defaults until billing enabled
3. **Implement proper retry logic:** Exponential backoff with jitter for rate limit errors
4. **Batch requests:** Reduce API calls through batching where supported
5. **Local caching:** Cache API responses to reduce redundant calls
6. **Monitor usage:** Set up alerts before hitting limits, not after

**Detection (warning signs):**
- Intermittent 403 errors
- Integration works for you but not users
- Approaching quota limits in Cloud Console

**Phase mapping:** Integration architecture in Phase 2. Plan quota strategy before building integrations.

**Sources:**
- [Google Cloud: OAuth Application Rate Limits](https://support.google.com/cloud/answer/9028764?hl=en)
- [Google Cloud: Capping API Usage](https://docs.cloud.google.com/apis/docs/capping-api-usage)
- [Google Workspace: Limits and Quotas](https://developers.google.com/workspace/admin/reports/v1/limits)

---

### Pitfall 9: Multi-Device Sync Conflicts

**What goes wrong:** Data diverges between devices. Edits lost. Duplicate entries. Inconsistent state after network interruption.

**Why it happens:** Last-write-wins without conflict resolution. No offline support. Sync interrupted mid-transaction.

**Consequences:**
- Users lose data they thought was saved
- Duplicated or conflicting entries
- Trust erosion ("I can't rely on this syncing")

**Prevention:**
1. **Conflict resolution strategy upfront:** Choose LWW, merge, CRDTs, or manual resolution based on data type
2. **UUIDs for everything:** Client-generated unique IDs avoid collision without central coordination
3. **Versioning/vector clocks:** Track causal relationships between changes
4. **Checkpoint system:** Track sync progress; resume from last successful point
5. **Offline-first architecture:** Cache locally, sync when connected, never lose user data
6. **Test network failures:** Simulate disconnection mid-sync; ensure graceful recovery

**Detection (warning signs):**
- Users reporting "it was different on my other device"
- Duplicate records appearing
- Data missing after sync

**Phase mapping:** Multi-device architecture in Phase 3+ (after single-device working). Can start with one device and add sync later.

**Sources:**
- [Medium: Designing Robust Data Sync for Multi-Device Apps](https://medium.com/@engineervishvnath/designing-a-robust-data-synchronization-system-for-multi-device-mobile-applications-c0b23e4fc0cb)
- [PixelFreeStudio: Best Practices for Real-Time Data Sync](https://blog.pixelfreestudio.com/best-practices-for-real-time-data-synchronization-across-devices/)
- [MoldStud: Cross-Device Syncing](https://moldstud.com/articles/p-implementing-cross-device-syncing-for-seamless-experiences)

---

### Pitfall 10: Hetzner Bandwidth Surprise

**What goes wrong:** Server bill 4x expected due to bandwidth overages after upgrade or region selection.

**Why it happens:** Surface pricing omits bandwidth limits. Different regions have wildly different included bandwidth (EU: 20TB vs US/Singapore: 1TB). Upgrades can reduce included bandwidth.

**Consequences:**
- $108 server becomes $462 monthly bill
- Budget planning failures
- Forced architecture changes to reduce bandwidth

**Prevention:**
1. **Choose EU datacenter:** 20TB included bandwidth vs 1TB elsewhere
2. **Understand bandwidth tiers:** 10 Gbps uplink = 20TB included; 1 Gbps = 330TB in some configs
3. **Compress data in transit:** Reduce bandwidth between desktop agents and server
4. **Cache aggressively:** Don't re-transfer data unnecessarily
5. **Monitor bandwidth daily:** Set alerts at 50%, 75%, 90% of included bandwidth

**Detection (warning signs):**
- Approaching included bandwidth limit mid-month
- High data transfer between desktop and server
- Screenshots being uploaded uncompressed

**Phase mapping:** Infrastructure decisions in Phase 1. Choose region carefully.

**Sources:**
- [Hetzner Cloud Pricing Calculator](https://costgoat.com/pricing/hetzner)
- [Hetzner Cloud Review 2026](https://www.bitdoze.com/hetzner-cloud-review/)
- [Fluence: Hetzner Pricing Analysis](https://www.fluence.network/blog/hetzner-dedicated-server-pricing-vs-fluence-virtual-servers/)

---

## Minor Pitfalls

Mistakes that cause annoyance but are recoverable.

---

### Pitfall 11: Tailscale CGNAT Conflicts

**What goes wrong:** Tailscale's 100.x.y.z addresses conflict with ISP or corporate VPN using same CGNAT range.

**Why it happens:** Tailscale uses 100.64.0.0/10 (CGNAT space). Some ISPs and VPNs also use this range.

**Prevention:**
1. **Check ISP/VPN before deployment:** Verify no CGNAT conflicts
2. **Use IPv6 if available:** Disable IPv4 in tailnet to avoid conflict
3. **Document workaround:** Know how to resolve before users hit it

**Sources:**
- [Tailscale: Security Hardening Best Practices](https://tailscale.com/kb/1196/security-hardening)
- [Tailscale: Troubleshooting Guide](https://tailscale.com/kb/1023/troubleshooting)

---

### Pitfall 12: Screenshot Storage Bloat

**What goes wrong:** Screenshots accumulate faster than expected, filling disk space. 1 screenshot/second = 86,400/day = ~50GB/day uncompressed.

**Prevention:**
1. **Aggressive compression:** JPEG quality 60-70% adequate for OCR
2. **Deduplication:** Don't store duplicate frames (diff detection)
3. **Retention policy:** Auto-delete after N days unless explicitly saved
4. **Tiered storage:** Hot (recent) on SSD, cold (old) compressed on HDD

---

### Pitfall 13: OAuth Token Refresh Failures

**What goes wrong:** Refresh tokens expire or revoke, breaking integrations silently. User doesn't know until they need the feature.

**Prevention:**
1. **Proactive token validation:** Check token validity periodically, not just on use
2. **Graceful re-auth flow:** Clear UX for re-authentication when tokens expire
3. **Notification of failures:** Alert user when integration breaks, don't fail silently

---

## Phase-Specific Warnings

| Phase | Topic | Likely Pitfall | Mitigation |
|-------|-------|----------------|------------|
| 1 | Desktop capture | Resource starvation | Adaptive capture, async processing, resource budgets |
| 1 | Screenshot storage | Privacy exposure | Encryption at rest from day one, biometric access |
| 1 | Infrastructure | Bandwidth costs | Choose EU Hetzner, monitor usage |
| 2 | RAG system | Retrieval quality | Hybrid search, metadata filtering, evaluation framework |
| 2 | Vector storage | Cost explosion | Quantization, dimension limits, data lifecycle |
| 2 | OCR pipeline | Accuracy cliff | Cloud OCR for complex layouts, test on real screenshots |
| 2 | MCP servers | Security vulnerabilities | Build your own, strict input validation, token isolation |
| 3 | Google integrations | Quota limits | Understand tiers, implement backoff, request increases early |
| 3 | Automation | Trust collapse | Tiered trust model, precision over recall, destructive action blocks |
| 4 | Multi-device | Sync conflicts | CRDT/conflict resolution, offline-first, checkpoint system |

---

## Jarvis-Specific Recommendations

Given the project constraints (privacy-critical, budget-conscious, no desktop slowdown):

### Non-Negotiable from Phase 1:
1. **Encryption at rest with biometric access** - Cannot be added later
2. **Resource-budgeted desktop agent** - Core constraint
3. **EU Hetzner region** - Cost control
4. **Tiered trust model design** - Architecture decision

### Can Iterate:
1. OCR accuracy (start local, add cloud for problem cases)
2. RAG retrieval quality (ship basic, tune based on real usage)
3. Multi-device sync (single device first, add later)

### Research Flags for Later Phases:
- Phase 2: Deep dive on specific vector DB choice
- Phase 3: Google API quota planning for specific integrations
- Phase 4: CRDT implementation for multi-device sync

---

## Sources Summary

### Official Documentation
- [MCP Security Best Practices](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices)
- [Microsoft Recall Privacy Controls](https://support.microsoft.com/en-us/windows/privacy-and-control-over-your-recall-experience-d404f672-7647-41e5-886c-a3c59680af15)
- [Tailscale Security Hardening](https://tailscale.com/kb/1196/security-hardening)
- [Google Cloud API Quotas](https://support.google.com/cloud/answer/9028764?hl=en)

### Security Research
- [DoublePulsar: Microsoft Recall Security Analysis](https://doublepulsar.com/microsoft-recall-on-copilot-pc-testing-the-security-and-privacy-implications-ddb296093b6c)
- [Palo Alto Unit 42: MCP Attack Vectors](https://unit42.paloaltonetworks.com/model-context-protocol-attack-vectors/)
- [Red Hat: MCP Security Risks](https://www.redhat.com/en/blog/model-context-protocol-mcp-understanding-security-risks-and-controls)

### Technical Deep Dives
- [Seven Failure Points in RAG (arXiv)](https://arxiv.org/html/2401.05856v1)
- [23 RAG Pitfalls](https://www.nb-data.com/p/23-rag-pitfalls-and-how-to-fix-them)
- [LocalLLM Hardware Guide](https://localllm.in/blog/ollama-vram-requirements-for-local-llms)
- [OCR Benchmark 2026](https://research.aimultiple.com/ocr-accuracy/)

### Industry Analysis
- [Netcraft: False Positive Tax](https://www.netcraft.com/blog/the-false-positive-tax-how-bad-automation-destroys-security-program-credibility/)
- [Pure Storage: Vector Storage Bloat](https://blog.purestorage.com/purely-technical/managing-vector-storage-bloat-insights-for-scalable-systems/)
- [Hetzner Cloud Review 2026](https://www.bitdoze.com/hetzner-cloud-review/)
