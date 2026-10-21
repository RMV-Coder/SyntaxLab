---
title: SyntaxLab Parser API
emoji: 🌳
colorFrom: blue
colorTo: yellow
sdk: docker
app_port: 7860
license: mit
short_description: Syntactic analysis API behind the SyntaxLab web app
---

# SyntaxLab Parser API

The analysis service behind [SyntaxLab](https://github.com/RMV-Coder/SyntaxLab), an open-source
app for learning syntax. It returns phrase-structure trees and dependency graphs from
statistical parsers (Stanza, trained on Universal Dependencies treebanks), runs the Earley
parser of the Algorithm Lab, and checks practice exercises.

This Space is generated from `services/parser-api` by `deploy/huggingface/prepare-space.sh`;
change the source repository, not this one.

- Liveness: `GET /health`
- Readiness (models loaded): `GET /ready`
- API reference: `GET /docs`, and `docs/api.md` in the source repository

Analyses are produced by statistical models and can be wrong. They are not checked by a
linguist.
