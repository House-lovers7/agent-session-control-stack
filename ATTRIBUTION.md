# Attribution

This repository is an integration / reference architecture.
It does not claim ownership of the underlying ideas or implementations, and it does not bundle any upstream code.

Credits:

- **[pxpipe](https://github.com/teamchong/pxpipe)** by [teamchong](https://github.com/teamchong) — compression layer: a local proxy that converts bulky context into images to reduce input tokens, with explicitly documented lossy trade-offs
- **[claude-code-session-health](https://github.com/House-lovers7/claude-code-session-health)** by [House-lovers7](https://github.com/House-lovers7) — health detection layer: closed-loop session health detection that lets the model itself propose `/compact`, a fresh session, or subagent delegation
- **[compact-plus](https://github.com/u-ichi/compact-plus)** by [u-ichi](https://github.com/u-ichi) — checkpoint and recovery layer: transcript backup, 10-section state capture before compaction, and recovery guidance injection after it

This project aims to document how these ideas can be composed safely across Claude Code and Codex.

---

本リポジトリは、上記の各 OSS を置き換えるものではありません。
各作者の実装とアイデアを尊重し、長時間 AI エージェント運用のための統合アーキテクチャとして「安全な組み合わせ方」を文書化するものです。上流のコードは同梱していません。

All factual claims about the upstream projects in this repository were verified against their READMEs and sources on 2026-07-05. If you are an upstream author and find anything misrepresented, please open an issue — corrections take priority.
