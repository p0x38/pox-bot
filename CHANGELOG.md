# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Bug Fixes
- Add names of each `uv lock --check`
([dfc15b7](https://github.com/p0x38/pox-bot/commit/dfc15b779d0f17a9a263b00fab5dc96e1600929f))
 by @p0x38

### CI
- Fix install method
([1a5eafc](https://github.com/p0x38/pox-bot/commit/1a5eafc07b1e16bb5f20e34ee7a95fe29f7e7861))
 by @p0x38

### Documentation
- Add conventional commits note
([691ba09](https://github.com/p0x38/pox-bot/commit/691ba093b1c9b3b916e0ecc9cf8330bf86b32407))
 by @p0x38
- Update CHANGELOG.md
([67b1bbe](https://github.com/p0x38/pox-bot/commit/67b1bbe6f84e2fefe58e1672c2aba427011088ac))
 by @p0x38

### Features
- Update OpenRouter adapter
([ab930ae](https://github.com/p0x38/pox-bot/commit/ab930ae6f29e14021148a97f843e4ca5d8dd97c7))
 by @p0x38

### Miscellaneous Chores
- Update cliff.toml
([42f4ac6](https://github.com/p0x38/pox-bot/commit/42f4ac69f45d0c9da063a844c6a236be2c1a0b24))
 by @p0x38

### Testing
- Update OpenRouter tests for Pygent adapter
([1f370e9](https://github.com/p0x38/pox-bot/commit/1f370e9118aac41a330cf7a340b905623e319b59))
 by @p0x38

## [1.1.0] - 2026-09-03

### Bug Fixes
- Improved error handling method for _on_tree_error
([79b92fb](https://github.com/p0x38/pox-bot/commit/79b92fb62ccf32376cec57011f74128e5d3d1545))
 by @p0x38
- Cliff.toml render syntax were invalid
([95f1ff3](https://github.com/p0x38/pox-bot/commit/95f1ff3f0c0aae098f890f009624f6f389bdbeb7))
 by @p0x38
- Activity.py will be not emitting error message when ConnectionClosed, ClientConnectionError or HTTPException was raised
([63b6e55](https://github.com/p0x38/pox-bot/commit/63b6e55b07982e460675f82445c7e5762644442a))
 by @p0x38
- Memory_manager.py will not log when collected objects was 0
([4760f66](https://github.com/p0x38/pox-bot/commit/4760f669aff0b062da1d9e1d9264e8f102b37ac6))
 by @p0x38
- Removed TTSEngineType from exceptions __init__.py because of it was unnessecary import syntax
([9ed6807](https://github.com/p0x38/pox-bot/commit/9ed680799b8649685eaf6504fe5703f3b23d7b83))
 by @p0x38
- Improve error handling
([23572f1](https://github.com/p0x38/pox-bot/commit/23572f1db7a1f5a9c3d18fdc90659f8cec1f75e6))
 by @p0x38
- Improve error handling
([e5126a1](https://github.com/p0x38/pox-bot/commit/e5126a1a422640109bd95d6f39c4a6382aadd956))
 by @p0x38
- Configure type checking paths
([fe663ba](https://github.com/p0x38/pox-bot/commit/fe663ba7a5319cae0ecf4f998a28f4fd16e528d6))
 by @p0x38
- Fix data type on database
([b0e1514](https://github.com/p0x38/pox-bot/commit/b0e151424ce0d0acf4a11f1941458c0631e2751e))
 by @p0x38
- Fix markov model scope not working
([5969973](https://github.com/p0x38/pox-bot/commit/59699730997f51aee0471b62c4f73be09cdcf140))
 by @p0x38
- Fix chatbot_runtime.py
([ce4626d](https://github.com/p0x38/pox-bot/commit/ce4626dab06cea40bab7b382d27eff1296a93675))
 by @p0x38
- Fix diagnostics stuff to work
([3bdcdd9](https://github.com/p0x38/pox-bot/commit/3bdcdd976362c069342dfa135a755ee71e1e3439))
 by @p0x38
- Register smart trigger extension
([0046aba](https://github.com/p0x38/pox-bot/commit/0046abad3bb5b485711d755f87151e8b9a46afbf))
 by @p0x38
- Use existing LLM service export
([072fddc](https://github.com/p0x38/pox-bot/commit/072fddc0c07100d72f71814f2e5a28aaee82c240))
 by @p0x38
- Prioritize explicit smart triggers
([0ca5b59](https://github.com/p0x38/pox-bot/commit/0ca5b597939546e58c836f34aeb5794f402f8552))
 by @p0x38
- Apply smart trigger cooldown to AI
([0541054](https://github.com/p0x38/pox-bot/commit/0541054043c47fcaae944838aafeb9d2625aefca))
 by @p0x38
- Preserve TF-IDF document ordering
([85eedb7](https://github.com/p0x38/pox-bot/commit/85eedb7454cc3a813300e96a87fe58e0b431512f))
 by @p0x38
- Add Discord mention sanitizer
([b385cca](https://github.com/p0x38/pox-bot/commit/b385ccab194f62c186f865b79895bb65bb14fc6b))
 by @p0x38
- Serialize saves and strip Discord mentions
([fede52f](https://github.com/p0x38/pox-bot/commit/fede52f5641c084f8527f1999726d76bed26b35b))
 by @p0x38
- Fix test file
([a642ad5](https://github.com/p0x38/pox-bot/commit/a642ad5438a51dcf0bc1240e23a6e2dc57f2d9b4))
 by @p0x38
- Honor configured LLM provider
([f1f3ad5](https://github.com/p0x38/pox-bot/commit/f1f3ad5ad6ecad5478f7d828fbc852e3a445c4e2))
 by @p0x38
- Fix provider settings not reflecting
([4c154fc](https://github.com/p0x38/pox-bot/commit/4c154fc839c8594a2cbd290a0bf1a712cec79da7))
 by @p0x38
- Remove try clause
([3f970fa](https://github.com/p0x38/pox-bot/commit/3f970faac02d56c479e67822b44398169392203d))
 by @p0x38

### Build
- Move some non-MIT compatible packages to optional dependencies
([a73c1da](https://github.com/p0x38/pox-bot/commit/a73c1da292356e64964c4458c45df74d5d50e51f))
 by @p0x38
- Fix dependencies for ci errors
([51f25d0](https://github.com/p0x38/pox-bot/commit/51f25d0c4755d1e17ea275633e000d1dfd14a767))
 by @p0x38
- Add uv lockfile
([ceab48e](https://github.com/p0x38/pox-bot/commit/ceab48eff6352a7bcba7262b0584f47744a05393))
 by @p0x38
- Bump astral-sh/setup-uv from 6 to 7
([bce5def](https://github.com/p0x38/pox-bot/commit/bce5def078f6a136eaa1d3e35350b86c83e45070))
 by @dependabot[bot]
- Bump github/codeql-action from 3 to 4
([92e1250](https://github.com/p0x38/pox-bot/commit/92e1250db4fe6fef9ff6ee0307ee8f487d6e3914))
 by @dependabot[bot]
- Bump actions/checkout from 4 to 7
([c2a1a4f](https://github.com/p0x38/pox-bot/commit/c2a1a4f8941eab47858cede3acf1ca2f04392d15))
 by @dependabot[bot]
- Bump actions/setup-python from 5 to 7
([f3f17a0](https://github.com/p0x38/pox-bot/commit/f3f17a03359f6c058156fbf1a507511de6f566e2))
 by @dependabot[bot]
- Remove conflicting openrouter dependency
([456a39c](https://github.com/p0x38/pox-bot/commit/456a39c03300abea7f4ed6d0823b46e2a73f41a9))
 by @p0x38
- Fix dependency metadata options
([803b790](https://github.com/p0x38/pox-bot/commit/803b790f1abdd25dd0e30d4a4aa1c1f44b9c13fb))
 by @p0x38

### CI
- Separate workflows
([d477e31](https://github.com/p0x38/pox-bot/commit/d477e31b2c0797166466f31e359ee4015137c214))
 by @p0x38
- Rename test to Test
([fae437a](https://github.com/p0x38/pox-bot/commit/fae437a7cdfe1d09bb314721a139878174a5bbc1))
 by @p0x38
- Update CI workflow files
([ab395ff](https://github.com/p0x38/pox-bot/commit/ab395ff85836b8eba08e8ef29b838b897916488b))
 by @p0x38
- Re-combine into ci.yml
([be4c0c0](https://github.com/p0x38/pox-bot/commit/be4c0c038ffee349e3dcb349230b006a2236423b))
 by @p0x38
- Update ci.yml and codeql.yml
([9953c9b](https://github.com/p0x38/pox-bot/commit/9953c9bb0e9d9f6b4e0b655286479bd8254df0f8))
 by @p0x38

### Documentation
- Generated CHANGELOG.md via git-cliff
([873ca67](https://github.com/p0x38/pox-bot/commit/873ca6711403c26b6161c830b0c5d9fa4c06e8f7))
 by @p0x38
- Add contributing guide
([0e94e55](https://github.com/p0x38/pox-bot/commit/0e94e55b8ef823bc00a781d44d345fd8192cc652))
 by @p0x38
- Remove unnecessary ignore comments
([e772fb8](https://github.com/p0x38/pox-bot/commit/e772fb8d854aa2c872c951ac0e03026264b181af))
 by @p0x38
- Add ignore comments and fixes
([b26bea8](https://github.com/p0x38/pox-bot/commit/b26bea82e6a554acf69a05f036798688577b8427))
 by @p0x38
- Track configurable LLM provider
([dee3752](https://github.com/p0x38/pox-bot/commit/dee3752ea7441d6256673eaadbe2df6e0646d3a8))
 by @p0x38

### Features
- Many stuff
([0797b5a](https://github.com/p0x38/pox-bot/commit/0797b5aead6692ef948bb284c78d299e3c40a19a))
 by @p0x38
- Many changes i can't describe sorry
([5d152fd](https://github.com/p0x38/pox-bot/commit/5d152fdde7a22457ee07d5902d354fa88bbcab66))
 by @p0x38
- Added TUI support by using textual
([8606a51](https://github.com/p0x38/pox-bot/commit/8606a51bd9cc09119e4a3586c0a88d2dd456d1ed))
 by @p0x38
- Added dashboard property for TUI with textual package
([2a69c4b](https://github.com/p0x38/pox-bot/commit/2a69c4b678f132ea48d01ac6b48015f16911f228))
 by @p0x38
- Added embed_exceptions for embed error displaying method in future use
([561e8b8](https://github.com/p0x38/pox-bot/commit/561e8b839f19f5881d9ccfc04a7505dc7084dc42))
 by @p0x38
- Added user_flags for Discord API's User flag feature
([e476abe](https://github.com/p0x38/pox-bot/commit/e476abe44d6bc6029fef21c03269d91b7d594ef3))
 by @p0x38
- Added Japanese translation for displaying of exception handling
([68a56b7](https://github.com/p0x38/pox-bot/commit/68a56b7f629cc6c2c392f69617b1f6c02355ec2e))
 by @p0x38
- Added more status texts
([62880e3](https://github.com/p0x38/pox-bot/commit/62880e30ef21e815cc71c36b6c8a7b2c0c66a928))
 by @p0x38
- Added many features
([b3f6919](https://github.com/p0x38/pox-bot/commit/b3f691977e4a994f61e41ecce7da4d3655739bf5))
 by @p0x38
- Added Chatbot Config
([4442ed1](https://github.com/p0x38/pox-bot/commit/4442ed1a61624b417247f0294530e66072ff45ce))
 by @p0x38
- Improve extension manager
([d137e98](https://github.com/p0x38/pox-bot/commit/d137e98b20ea49a87ae69f80bb4701f53aee1428))
 by @p0x38
- Add MarkovGenerator
([1b57016](https://github.com/p0x38/pox-bot/commit/1b570166625a430002fbda4ff7d608c50555c26f))
 by @p0x38
- Add MarkovModel
([695d942](https://github.com/p0x38/pox-bot/commit/695d942286758f7eddddec94629ccb6b83802212))
 by @p0x38
- Add MarkovGenerator
([9072742](https://github.com/p0x38/pox-bot/commit/90727425dc9d288619d77d179ba2dee17aa1085f))
 by @p0x38
- Add MarkovStorage
([fc4ddf3](https://github.com/p0x38/pox-bot/commit/fc4ddf3c289ef8ca02002490f144ff27b87fad20))
 by @p0x38
- Add MarkovTokenizer
([c1dc36d](https://github.com/p0x38/pox-bot/commit/c1dc36d91c657981d002184727bb12a20ca881f7))
 by @p0x38
- Add markov-related settings
([4caaef4](https://github.com/p0x38/pox-bot/commit/4caaef412edc8a0e188ff7a265c2061b015a1015))
 by @p0x38
- Add markov-based chat system
([d089593](https://github.com/p0x38/pox-bot/commit/d0895932990b0443974401ea8ee1464e9700b047))
 by @p0x38
- Add chat feature i guess
([8a437d4](https://github.com/p0x38/pox-bot/commit/8a437d41fe013276b8aba2391a089c927373923f))
 by @p0x38
- Add lightweight dialogue memory
([d8b6078](https://github.com/p0x38/pox-bot/commit/d8b6078e160b7f50b2bf4c6d072349590b8d084d))
 by @p0x38
- Integrate dialogue retrieval
([fa545a0](https://github.com/p0x38/pox-bot/commit/fa545a0a43ae37691fbaf30c81d7cfe470695d3e))
 by @p0x38
- Improve markov-based chat system
([12fda15](https://github.com/p0x38/pox-bot/commit/12fda151b90fe9766986a2ca5ad27b975ebca92a))
 by @p0x38
- Add runtime reload control
([7105529](https://github.com/p0x38/pox-bot/commit/71055298783ae4ecce48c6ba2c9ade7793624ee5))
 by @p0x38
- Add Markov learning diagnostics
([8657188](https://github.com/p0x38/pox-bot/commit/8657188b8f6451a4dbc41f1f08ca7f9b29f15ae0))
 by @p0x38
- Add backend abstraction
([64a5d8f](https://github.com/p0x38/pox-bot/commit/64a5d8f2351074b9cebdd67c68f4998d7dbbd7e8))
 by @p0x38
- Add Markovify generation backend
([7858a1e](https://github.com/p0x38/pox-bot/commit/7858a1e387d361e923f9fab9898a7bfb8212b62e))
 by @p0x38
- Route generation through backend
([49280bc](https://github.com/p0x38/pox-bot/commit/49280bcb97e4a77349ce0101a396e9d3bf03f6bc))
 by @p0x38
- Add smart trigger evaluator
([919001b](https://github.com/p0x38/pox-bot/commit/919001b3983785583e5f8254b9cb90d9e1606ba3))
 by @p0x38
- Add smart conversational triggers
([3c67d60](https://github.com/p0x38/pox-bot/commit/3c67d606b423aca16d0eeec8af356b67adb4fbd2))
 by @p0x38
- Add lightweight TF-IDF index
([280bf1e](https://github.com/p0x38/pox-bot/commit/280bf1ebd640a71a30eaba7db95a03b52bd92176))
 by @p0x38
- Replace fuzzy dialogue retrieval with TF-IDF
([39c523d](https://github.com/p0x38/pox-bot/commit/39c523dcafd8cfa37a9689dce02f5dcbb035ff5f))
 by @p0x38
- Integrate Pygent agent
([0efdc87](https://github.com/p0x38/pox-bot/commit/0efdc87ef842a1a3847eadc919b43650bb2abd96))
 by @p0x38
- Add Pygent Ollama support
([ce9301f](https://github.com/p0x38/pox-bot/commit/ce9301f066a541a5ee35ecd53d7a5a39ccff6462))
 by @p0x38
- Add configurable LLM provider
([39ff00f](https://github.com/p0x38/pox-bot/commit/39ff00f0798ad167516ba4c995a0177490a65493))
 by @p0x38

### Miscellaneous Chores
- Some unusual or smth else change
([2ad6c68](https://github.com/p0x38/pox-bot/commit/2ad6c68efb3bb8136dc06abe9a49cd2c2842f88b))
 by @p0x38
- Biggest changes ever I did
([aacb3f2](https://github.com/p0x38/pox-bot/commit/aacb3f2200345687e700204b6f80a0b7de86bace))
 by @p0x38
- Remove unnessary log data
([a71a1ec](https://github.com/p0x38/pox-bot/commit/a71a1ec8f4a55dadad278aa4c07f7abe578f5188))
 by @p0x38
- Mass
([a5f071f](https://github.com/p0x38/pox-bot/commit/a5f071f9bd04c5dbda6ebba37c8dc1a4b064046c))
 by @p0x38
- Mass 2
([97e1d97](https://github.com/p0x38/pox-bot/commit/97e1d9729782f29569436816331e6e7bb7bd098a))
 by @p0x38
- Updated .gitignore
([fc41995](https://github.com/p0x38/pox-bot/commit/fc41995062f37d63029039bfb6da36b6d6a89307))
 by @p0x38
- Updated Dockerfile
([ba217b8](https://github.com/p0x38/pox-bot/commit/ba217b8954362615c2b51d50d51f3c024c4a1464))
 by @p0x38
- Updated dependencies
([6ad2039](https://github.com/p0x38/pox-bot/commit/6ad20392da1682756efd7b312c6c7c20b146d6a9))
 by @p0x38
- Updated VSCode settings; unrelated to the codebase
([e82095e](https://github.com/p0x38/pox-bot/commit/e82095ebf99b95910a1f81de04e6e43ea1218e5d))
 by @p0x38
- Refactor extension names
([932ad3a](https://github.com/p0x38/pox-bot/commit/932ad3a674342a83b1b28a0418827c397bb8619b))
 by @p0x38
- Update ruff.toml
([5dcf418](https://github.com/p0x38/pox-bot/commit/5dcf418ac23481d817eaa0e5583a0d64f00b03ac))
 by @p0x38
- Add SECURITY.md
([9082a78](https://github.com/p0x38/pox-bot/commit/9082a78599734ee0e43f1103dc80ebeea2dc2fcd))
 by @p0x38
- Remove unnecessary stuffs
([45f0ac1](https://github.com/p0x38/pox-bot/commit/45f0ac14cf5c23388205533fb8b958e01e1f5e5a))
 by @p0x38
- Update todo
([f352e7f](https://github.com/p0x38/pox-bot/commit/f352e7f96f84894e227b83aabf99cbcb74a4cc41))
 by @p0x38
- Settings change
([47f786e](https://github.com/p0x38/pox-bot/commit/47f786ef66d020ba4a17938bcf4c634254e6b406))
 by @p0x38
- Add discord utility package
([cc26719](https://github.com/p0x38/pox-bot/commit/cc2671924a7325a1a5a07a3cf48e1f0ab769b55f))
 by @p0x38
- Update .gitignore
([0246e9e](https://github.com/p0x38/pox-bot/commit/0246e9ec07e1e522d73199fc44a4347ca37de996))
 by @p0x38
- Update settings.json in local reason
([cb53256](https://github.com/p0x38/pox-bot/commit/cb53256bf8c853312f4d6e40ac6a18ac75eba932))
 by @p0x38
- Update uv lockfile
([2134c63](https://github.com/p0x38/pox-bot/commit/2134c63e2365ceb650045840223ca8d72b7f501c))
 by @p0x38
- Bump to 1.1.0
([715119c](https://github.com/p0x38/pox-bot/commit/715119cecb5f5bc7c8b8633616e56f70d9d70869))
 by @p0x38

### Other
- )
([d1dbdfe](https://github.com/p0x38/pox-bot/commit/d1dbdfe756cabe60162a51ea53738bb1ea9d6f92))
 by @p0x38
- 3
([872862d](https://github.com/p0x38/pox-bot/commit/872862d84711a5694274459af13d947ab060d62f))
 by @p0x38
- 3
([6711a66](https://github.com/p0x38/pox-bot/commit/6711a665e706f56cdf1f30aeefc38c1e05a34aed))
 by @p0x38
- I18n support
([22f5b0b](https://github.com/p0x38/pox-bot/commit/22f5b0ba09be0be532d726a2767b40488982d4c1))
 by @p0x38

### Refactor
- Renamed llm_chat.py to chatbot.py for future use
([75847c1](https://github.com/p0x38/pox-bot/commit/75847c1ed63cb639296facd0619650e00f53ab6c))
 by @p0x38
- Refactor error message
([ebd6102](https://github.com/p0x38/pox-bot/commit/ebd6102b800a8d7563f307835481a469e4e39ddf))
 by @p0x38
- Simplify runtime reload response
([88c0595](https://github.com/p0x38/pox-bot/commit/88c0595e9c8c2df5ed9af02bd1978e3efe0cd216))
 by @p0x38
- Keep native backend independent
([0482e4e](https://github.com/p0x38/pox-bot/commit/0482e4eee8578b24ff929e698f79634e667d5b6e))
 by @p0x38
- Expose backend generator
([ad8e395](https://github.com/p0x38/pox-bot/commit/ad8e39544c09448bdaeb384640fe74689329e751))
 by @p0x38
- Make smart trigger evaluation conservative
([8cd73f5](https://github.com/p0x38/pox-bot/commit/8cd73f55fdac9af539e5b4dfaea27d63535341d9))
 by @p0x38
- Keep mention sanitization in tokenizer
([20dce6b](https://github.com/p0x38/pox-bot/commit/20dce6bac4074a6ad710f5157b769c5c390144a4))
 by @p0x38
- Route OpenRouter through Pygent
([5f470de](https://github.com/p0x38/pox-bot/commit/5f470deec1067d37e077e4887fde1a2eca9ab58b))
 by @p0x38
- Refactor pyproject.toml
([8aae30c](https://github.com/p0x38/pox-bot/commit/8aae30cb5c8520377748f4f5ab5f46a4ce420f15))
 by @p0x38

### Revert
- Remove unused discord utility package
([31c3284](https://github.com/p0x38/pox-bot/commit/31c3284f932b2cd6f843b60dc0f5b7ef16a485f2))
 by @p0x38

### Testing
- Add test of LLM error handling
([94f9d98](https://github.com/p0x38/pox-bot/commit/94f9d98b845c23a6d1621a633c847d5b89459825))
 by @p0x38
- Add test of OpenRouter function
([b8ffa5b](https://github.com/p0x38/pox-bot/commit/b8ffa5bebf69aaa2b5e8f3d491a739c73b0daf01))
 by @p0x38
- Update entire codebase
([0bd4bcd](https://github.com/p0x38/pox-bot/commit/0bd4bcd9e9d3dcf6e7643576197bb42af9dabed9))
 by @p0x38
- Cover Markov runtime cache reload
([72b3de4](https://github.com/p0x38/pox-bot/commit/72b3de4f82c163361712e74ece5f57df39cc0c33))
 by @p0x38
- Cover Markov config round-trip
([30cb861](https://github.com/p0x38/pox-bot/commit/30cb8618bd5dd3c498f7fcd3a300f8a0f6edf015))
 by @p0x38
- Cover Markovify backend
([c75ca62](https://github.com/p0x38/pox-bot/commit/c75ca62d41f7b7ee79cb372d0dcb3fb3d0cd5831))
 by @p0x38
- Refine smart trigger rules
([5c26013](https://github.com/p0x38/pox-bot/commit/5c260135c0526725f8657344d78e7e542e9ece11))
 by @p0x38
- Add smart trigger coverage
([d88e2c7](https://github.com/p0x38/pox-bot/commit/d88e2c70d58aca6a476acc94131f8b8c5629462f))
 by @p0x38
- Cover TF-IDF similarity
([1cfd549](https://github.com/p0x38/pox-bot/commit/1cfd5495658339d0647aa7f90a20d698119a4de9))
 by @p0x38
- Cover TF-IDF dialogue retrieval
([a3441bc](https://github.com/p0x38/pox-bot/commit/a3441bca27da298a39f20f02b2ab349374af271f))
 by @p0x38
- Cover Discord mention sanitization
([88ea2e3](https://github.com/p0x38/pox-bot/commit/88ea2e3d74f0d15178508a72d3f1b6a68ae2150e))
 by @p0x38
- Cover configured LLM provider
([b796c45](https://github.com/p0x38/pox-bot/commit/b796c45fc2d3b02e17031bcad1646ab9fc33fbb0))
 by @p0x38
- Focus provider configuration coverage
([49aefbf](https://github.com/p0x38/pox-bot/commit/49aefbfa826c82fa92e9561b57108a0c7fabdcd2))
 by @p0x38

### New Contributors
* @p0x38 made their first contribution
* @dependabot[bot] made their first contribution
* @crowdin-bot made their first contribution

[unreleased]: https://github.com/p0x38/pox-bot/compare/v1.1.0...HEAD

<!-- generated by git-cliff -->
