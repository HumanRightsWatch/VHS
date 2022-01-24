# Video downloading platform

Download video from various sources.

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Black code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

License: GPL v3

## Settings
To learn how to change application's settings, please refer
to [the Cookiecutter documentation](http://cookiecutter-django.readthedocs.io/en/latest/settings.html).

## Basic Commands

### Setting Up Your Users
- To create a **normal user account**, just go to Sign Up and fill out the form. Once you submit it, you\'ll see a
  \"Verify Your E-mail Address\" page. Go to your console to see a simulated email verification message. Copy the link
  into your browser. Now the user\'s email should be verified and ready to go.

- To create an **superuser account**, use this command:

```bash
$ python manage.py createsuperuser
```

For convenience, you can keep your normal user logged in on Chrome and your superuser logged in on Firefox (or similar),
so that you can see how the site behaves for both kinds of users.

### Type checks
Running type checks with mypy:

```bash
$ mypy video_downloading_platform
```

### Test coverage
To run the tests, check your test coverage, and generate an HTML coverage report:

```bash
$ coverage run -m pytest
$ coverage html
$ open htmlcov/index.html
```

#### Running tests with py.test
```bash
$ pytest
```

### Live reloading and Sass CSS compilation
To learn how to use live reloading and Sass CSS compilation, please refer
to [the Cookiecutter documentation](http://cookiecutter-django.readthedocs.io/en/latest/live-reloading-and-sass-compilation.html).

## Deployment
The following details how to deploy this application.

### Docker
To learn how to deploy this application with Docker, please refer
to [the Cookiecutter documentation](http://cookiecutter-django.readthedocs.io/en/latest/deployment-with-docker.html).

### Azure
To learn how to deploy this application on Microsoft Azure, please refer to [our step-by-step guide](doc/azure.md).

## Custom Bootstrap Compilation
The generated CSS is set up with automatic Bootstrap recompilation with variables of your choice. Bootstrap v4 is
installed using npm and customised by tweaking your variables in
`static/sass/custom_bootstrap_vars`.

You can find a list of available
variables [in the bootstrap source](https://github.com/twbs/bootstrap/blob/v4-dev/scss/_variables.scss), or get
explanations on them in the [Bootstrap docs](https://getbootstrap.com/docs/4.1/getting-started/theming/). Bootstrap's
javascript as well as its dependencies is concatenated into a single file: `static/js/vendors.js`.
