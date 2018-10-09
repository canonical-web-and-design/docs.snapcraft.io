# Discourse docs

[![CircleCI build status](https://circleci.com/gh/canonical-websites/discourse-docs.snapcraft.io.svg?style=shield)][circleci] [![Code coverage](https://codecov.io/gh/canonical-websites/discourse-docs.snapcraft.io/branch/master/graph/badge.svg)][codecov]

A basic website application to present the content of a Discourse installation as a documentation website.

Initially, this presents the contents of https://forum.snapcraft.io/c/doc as a website looking similar to https://docs.snapcraft.io/, but this is under active development and will change in the future to be more configurable for other Discourse forums, e.g. https://discourse.maas.io and https://discourse.jujucharms.com.

## Usage

After [installing Docker](https://docs.docker.com/install/), run:

``` bash
./run
```

And visit http://127.0.0.1:8029 in your browser.

[circleci]: https://circleci.com/gh/canonical-webteam/discourse-docs.snapcraft.io "CircleCI build status"
[codecov]: https://codecov.io/gh/canonical-webteam/discourse-docs.snapcraft.io "Code coverage"
