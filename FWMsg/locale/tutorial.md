# How to Create Translations

## Introduction

This guide will help you translate German text to English in a special file called `django.po`. You don't need any programming knowledge - just basic text editing skills and knowledge of both languages.

**File location:** `/locale/en/LC_MESSAGES/django.po`

This file contains all translations from German to English for the application.

---

## Understanding the File Structure

Each translation entry in the file looks like this:

```po
#: BW/forms.py:26
msgid "Das Passwort erneut eingeben."
msgstr "Please enter the password again."
```

Here's what each line means:

| Line | Meaning |
|------|---------|
| `#: BW/forms.py:26` | **Location**: Shows where this text appears in the application. You can ignore this - it's just for reference. |
| `msgid "..."` | **Original text**: The German text that needs to be translated. **Never change this line!** |
| `msgstr "..."` | **Translation**: This is where the English translation goes. **This is what you edit.** |

**Important rule:** Only edit the text inside the quotes `"..."` on the `msgstr` line. Never modify anything else!

---

## Case 1: Translation Already Exists

```po
#: BW/forms.py:26
msgid "Das Passwort erneut eingeben."
msgstr "Please enter the password again."
```

**What to do:**
1. Read the German text (`msgid`)
2. Read the English translation (`msgstr`)
3. Check if the translation is correct and makes sense
4. If it's correct, move on to the next entry
5. If it's wrong, correct the text between the quotes on the `msgstr` line

---

## Case 2: Translation is Missing

```po
#: ORG/templates/baseOrg.html:118 TEAM/templates/baseTeam.html:69
msgid "Karte"
msgstr ""
```

Notice that `msgstr ""` is empty - the quotes have nothing between them.

**What to do:**
1. Read the German text: "Karte" means "Map"
2. Type the English translation between the quotes

**After your edit:**

```po
#: ORG/templates/baseOrg.html:118 TEAM/templates/baseTeam.html:69
msgid "Karte"
msgstr "Map"
```

---

## Case 3: Fuzzy Entries (Outdated Translations)

```po
#: ORG/templates/homeOrg_2.html:571 TEAM/templates/teamHome.html:419
#, fuzzy
#| msgid "Neue Posts"
msgid "Alle Posts"
msgstr "New Posts"
```

**What does "fuzzy" mean?**
The word `#, fuzzy` means the translation is outdated. The original German text was changed, but the old English translation is still there. The system is warning you: "This translation might be wrong!"

**How to read this entry:**
- `#| msgid "Neue Posts"` = The **old** German text (crossed out, for reference only)
- `msgid "Alle Posts"` = The **new/current** German text
- `msgstr "New Posts"` = The **old** English translation (probably wrong now)

In this example:
- Old German: "Neue Posts" (New Posts)
- New German: "Alle Posts" (All Posts)
- Current translation: "New Posts" ← This is wrong now!

**What to do:**
1. Look at the **current** `msgid` ("Alle Posts")
2. Write the correct translation for **that** text
3. **Delete** the `#, fuzzy` line
4. **Delete** the `#| msgid "..."` line (the old text reference)

**After your edit:**

```po
#: ORG/templates/homeOrg_2.html:571 TEAM/templates/teamHome.html:419
msgid "Alle Posts"
msgstr "All Posts"
```

---

## Case 4: Original Text is Already in English

```po
#: survey/templates/survey/admin_survey_list.html:13
msgid "All Surveys"
msgstr ""
```

Sometimes the original text is already in English (like "Dashboard", "Home", "Email", etc.).

**What to do:**
You have two options:

**Option A:** Leave it empty (recommended)

```po
msgid "All Surveys"
msgstr ""
```

When `msgstr` is empty, the system automatically uses the `msgid` text.

**Option B:** Copy the same text

```po
msgid "All Surveys"
msgstr "All Surveys"
```

Both options work the same way. Choose whichever you prefer.

---

## Case 5: Obsolete Entries (Old, Unused Text)

```po
#~ msgid "Telefon Einsatzland"
#~ msgstr "Phone deployment country"
```

Notice that both lines start with `#~`. This means the text is **no longer used** in the application. It was removed from the code but kept in the file for reference.

**What to do:**
Nothing! Leave these entries exactly as they are. Don't translate them, don't delete them.

---

## Case 6: Multi-Line Translations

Sometimes a translation spans multiple lines:

```po
#: BW/forms.py:20
msgid ""
"Das Passwort muss folgende Anforderungen erfüllen:<br>• Mindestens 8 Zeichen "
"lang<br>• Mindestens ein Großbuchstabe (A-Z)"
msgstr ""
"Your password must meet the following requirements:<br>• At least 8 "
"characters long<br>• At least one uppercase letter (A-Z)"
```

**How it works:**
- The first line has empty quotes: `msgid ""`
- The actual text continues on the following lines, each in its own quotes
- The same pattern applies to `msgstr`

**What to do:**
1. Translate each line separately
2. Keep the same structure (line breaks in similar places)
3. Keep any HTML tags like `<br>` exactly as they are
4. Make sure each line starts and ends with quotes `"..."`

---

## Special Characters and Formatting

### Keep These Exactly As They Are

| Character/Code | Meaning | Example |
|---------------|---------|---------|
| `<br>` | Line break (HTML) | Keep in same position |
| `%s` | Placeholder for text | "Hello %s" → "Hallo %s" |
| `%(name)s` | Named placeholder | "Welcome %(user)s" |
| `%d` | Placeholder for number | "%d items" |
| `\n` | Line break (code) | Keep as is |
| `&nbsp;` | Space (HTML) | Keep as is |

**Example:**

```po
msgid "Willkommen %(username)s! Du hast %d neue Nachrichten."
msgstr "Welcome %(username)s! You have %d new messages."
```

The `%(username)s` and `%d` must stay exactly the same in the translation!

---

## Quick Reference: What To Do

| Situation | Action |
|-----------|--------|
| Translation exists and is correct | Move on, nothing to do |
| Translation exists but is wrong | Fix the `msgstr` text |
| Translation is missing (`msgstr ""`) | Add the English translation |
| Entry has `#, fuzzy` | Update translation, remove `#, fuzzy` and `#| msgid` lines |
| Original is already English | Leave `msgstr` empty or copy the text |
| Entry starts with `#~` | Ignore, don't change anything |

---

## Tips for Good Translations

1. **Be consistent**: If you translate "Benutzer" as "User" once, use "User" everywhere
2. **Match the tone**: If the German is formal, keep the English formal too
3. **Keep it short**: Button labels and menu items should be brief
4. **Don't translate names**: Product names, brand names stay the same
5. **Test context**: The location hint (`#: path/to/file`) can help you understand where the text appears

---

## Common Mistakes to Avoid

- **Don't change `msgid`** - Only edit `msgstr`
- **Don't delete entries** - Even if they look unnecessary
- **Don't forget quotes** - Every translation needs quotes around it
- **Don't remove placeholders** - Keep `%s`, `%d`, `%(name)s` exactly as they are
- **Don't break the file structure** - Keep each entry properly formatted

---

## How to Save Your Work

1. After making changes, save the file (Ctrl+S or Cmd+S)
2. Make sure the file encoding stays as **UTF-8**
3. If using a text editor, don't let it add extra formatting

---

## Need Help?

If you're unsure about a translation:
- Check the file location (`#: path/to/file`) for context
- Look at similar translations in the file for consistency
- When in doubt, leave a note and ask for clarification

Good luck with the translations!