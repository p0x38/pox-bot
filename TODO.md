# TODO.md

## Done

- [x] Add `/stats wordcloud`
- [x] Add `/stats active_pattern`
- [x] Add `/economy coinflip`
- [x] Add `/moderation slowmode`

## Work In Progress

- [ ] Improve nMarkov dialogue memory
- [ ] Integrate Pygent into the AI chatbot runtime
  - [x] Add the Pygent-backed OpenRouter adapter
  - [x] Add the Pygent-backed Ollama adapter
  - [x] Keep the existing ChatbotCog interface
  - [ ] Regenerate `uv.lock` with the Pygent dependency
  - [ ] Add integration tests
  - [ ] Replace the legacy AI provider dependencies
  - [x] Use `LLM_CONFIG__PROVIDER_TYPE` for provider selection

## Planned

- [ ] Add `/stats top_activedays`
- [ ] Add `/economy rob <user>`
- [ ] Add `/economy invest`
- [ ] Add `/tts voice_preset`
- [ ] Add `/tts dictionary add <word> <pronounce>`
- [ ] Add `/detect compatibility <user1> <user2>`
- [ ] Improve nMarkov dialogue memory
  - [ ] Prevent duplicate dialogue entries
  - [ ] Improve similarity scoring
  - [ ] Add configurable confidence threshold
  - [ ] Improve bot mention stripping
  - [ ] Track response usage/frequency
  - [ ] Add dialogue statistics to `/chatbot status`
- [ ] Add support for Matrix protocol
