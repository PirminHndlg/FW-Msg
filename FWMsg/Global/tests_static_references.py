import re
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase

STATIC_TAG = re.compile(r"""\{%\s*static\s+(['"])([^'"]+)\1\s*%\}""")

# Known dead references (source files removed in cdf2ed9e). css/base.css may still be served
# from an old collectstatic output, so removing the <link> could change the page styling.
KNOWN_MISSING = {
    'FW/templates/base.html: css/base.css',
    'seminar/templates/usersOverview.html: css/usersOverview.css',
}


class StaticReferencesTests(SimpleTestCase):
    """Every literal {% static '...' %} in a template must resolve to a file.

    Catches frontend dependency updates (npm) that move or remove files,
    e.g. FullCalendar 7 no longer shipping index.global.min.js.
    """

    def test_all_static_references_exist(self):
        base_dir = Path(settings.BASE_DIR)
        missing = []
        for template in sorted(base_dir.glob('*/templates/**/*.html')):
            for match in STATIC_TAG.finditer(template.read_text(encoding='utf-8')):
                path = match.group(2)
                reference = f'{template.relative_to(base_dir)}: {path}'
                if reference not in KNOWN_MISSING and not finders.find(path):
                    missing.append(reference)

        self.assertEqual(missing, [], 'Static files not found:\n' + '\n'.join(missing))
