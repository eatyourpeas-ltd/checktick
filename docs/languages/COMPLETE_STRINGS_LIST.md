# Complete List of Translatable Strings

**Total Strings:** 320 unique English strings
**Last Updated:** January 2025

This document contains every string that needs translation in the CheckTick application, organized by category. Use this as a reference when creating translations for any language.

---

## Category 1: Authentication & Account Management (32 strings)

User authentication, login, signup, password management, and account creation.

1. Sign up
2. Login to start
3. Email preferences updated successfully.
4. There was an error updating your email preferences.
5. Authenticated: login required · Public: open link · Unlisted: secret link · Invite token: one-time codes
6. Admin login
7. Username
8. Password
9. Forgotten your password or username?
10. Logout
11. Forgot password?
12. Password updated
13. Your password has been changed successfully.
14. Change password
15. Change your password
16. Save new password
17. Password reset complete
18. Your password has been set. You can now log in with your new password.
19. Go to login
20. This password reset link is invalid or has expired.
21. Reset email sent
22. Check your email
23. If an account exists with that email, we've sent a password reset link. Please follow the instructions to choose a new password.
24. In development, the reset email is printed to the console.
25. Reset your password
26. Enter the email address associated with your account.
27. Create your account
28. Sign up to start creating surveys and collecting responses.
29. Account Type
30. Organisation Account
31. Create account
32. Already have an account?

---

## Category 2: Survey Management (152 strings)

Survey creation, editing, publishing, dashboard, groups, questions, tokens, encryption, and deletion.

1. This application is in development currently and should NOT be used for live surveys at the moment.
2. Surveys for health care
3. Go to Surveys
4. Drag-and-drop groups and questions, apply DaisyUI themes per survey, and control access with roles.
5. Create a survey
6. Invite your team, scope visibility by organisation and survey membership, and manage participation securely.
7. Manage surveys
8. Monitor dashboards, export CSV, and audit changes. Everything runs on a secure SSR stack.
9. View dashboards
10. Organisation created. You are now an organisation admin and can host surveys and build a team.
11. Question Group Builder
12. Survey Dashboard
13. All Questions
14. Groups
15. Create and manage groups, then add questions inside each group.
16. Open a group
17. Import questions
18. Overwrite survey questions?
19. Groups and questions are assigned unique IDs as you edit. Use these IDs to reason about branching later.
20. Start typing (or use the sample markdown) to see the survey structure.
21. `# Group Title`, followed by a line for the group description
22. `## Question Title`, followed by a line for the question description
23. Optional: Required questions
24. Mark a question as required by adding an asterisk `*`
25. Required questions must be answered before the form can be submitted
26. Place the asterisk immediately after the question title text
27. Works with all question types
28. Optional: Collections with REPEAT
29. To mark a group as repeatable, add a line with **REPEAT** (or **REPEAT-5** to cap it) immediately above the group heading.
30. To define a child collection nested under a repeatable parent, indent with `>` and add **REPEAT** above the child group:
31. Use `>` before REPEAT and the group heading to indicate one level of nesting.
32. Groups without REPEAT are normal, non-collection groups.
33. Optional: Questions with conditional branching
34. Branching rules must start with `? when` and reference a question or group ID in curly braces.
35. Operators: `equals`, `not_equals`, `contains`, `not_contains`, `greater_than`, `less_than`.
36. Create Survey
37. Create a new survey
38. Name
39. Description
40. If left blank, a slug will be generated from the name.
41. I confirm no **patient-identifiable data** is collected in this survey
42. Keep track of survey status, number of responses and control styling.
43. Draft: build only · Published: accept submissions · Closed: stop submissions
44. Status
45. Total responses
46. No submissions yet
47. Survey style
48. Max responses
49. Require CAPTCHA for anonymous submissions
50. Publish settings
51. Save publish settings
52. Once deleted, all data, responses, groups, and permissions will be \npermanently removed. This action cannot be undone.
53. Delete this survey
54. You are about to permanently delete the survey:
55. Deleting this survey will permanently remove:
56. All survey data and responses
57. All associated groups and questions
58. All collection and publication records
59. All access permissions and tokens
60. To confirm deletion, please type the survey name exactly as shown above:
61. Type survey name here
62. You must type the survey name to confirm deletion.
63. Delete Survey Permanently
64. Manage Questions
65. Question Groups
66. Question Group
67. Questions in this group
68. No questions in this group yet.
69. Question Groups are reusable sets of questions. Arrange them here to control \nthe order in which participants see them.
70. Tip: Select groups by clicking their row or checkbox, then click 'Create \nrepeat' to set a name. Selected groups become part of the repeat.
71. Selected for repeat
72. Remove this group from its repeat?
73. Delete this group?
74. Delete
75. No groups yet. Create one to get started.
76. Create repeat from selection
77. selected
78. Back to dashboard
79. Create new question group
80. New group name
81. Create
82. Cancel
83. No surveys yet.
84. Survey users
85. Back to survey
86. Your response has been recorded.
87. Unlock Survey
88. Survey key
89. Enter the one-time survey key to decrypt sensitive fields for this session.
90. Unlock
91. Unlock this survey using your password or recovery phrase. The encryption key will be stored securely in your session.
92. Password
93. Recovery Phrase
94. Encryption Password
95. Enter your encryption password
96. This is the password you set when encrypting the survey.
97. Forgot your password? Switch to the Recovery Phrase tab.
98. Unlock with Password
99. Recovery Hint
100. 12-Word Recovery Phrase
101. Enter your 12-word recovery phrase (spaces between words)
102. Enter all 12 words separated by spaces. Capitalization and extra spaces don't matter.
103. Security Notice
104. Recovery phrase usage is logged for security audit purposes.
105. Unlock with Recovery Phrase
106. This survey uses legacy encryption. Enter your encryption key below.
107. Survey Key
108. This survey uses the older encryption format. Consider upgrading to password + recovery phrase encryption.
109. About Survey Unlocking
110. Unlocking allows you to view and manage encrypted survey data in this browser session. The encryption key is stored securely in your session and never transmitted over the network unencrypted.
111. Set Encryption Password
112. To publish this survey with encryption enabled, you must set a password.
113. Encryption password
114. Confirm password
115. Passwords do not match.
116. Recovery Hint (Optional)
117. A hint to help you remember your recovery phrase (shown during unlock)
118. Technical Details
119. Your password encrypts the survey key using Scrypt (n=2^14). A 12-word BIP39 recovery phrase is also generated, which can decrypt the key if you forget your password.
120. Set Password and Generate Recovery Phrase
121. Never share these with anyone!
122. Your Encryption Keys
123. This page will only be shown once. Please save this information securely.
124. Password encryption set successfully
125. 12-Word Recovery Phrase
126. Write down these words in order. You'll need them to recover access if you forget your password.
127. Recovery Phrase (one word per box)
128. Copy Recovery Phrase
129. Recovery phrase copied!
130. Download as Text File
131. Print This Page
132. 64-Character Hex Key (Advanced)
133. This is the raw encryption key. Store it separately as an additional backup.
134. Copy Hex Key
135. Hex key copied!
136. What happens next?
137. You can now unlock the survey using either your password or the recovery phrase. If you lose both, the encrypted data cannot be recovered.
138. Continue to Survey Dashboard
139. Survey unlocked with password.
140. Invalid password.
141. Survey unlocked with recovery phrase.
142. Invalid recovery phrase.
143. Invite Tokens
144. Invite tokens
145. Token
146. Created
147. No tokens yet.
148. Manage invite tokens
149. Invite token
150. Add user to survey
151. No surveys yet
152. Survey slug
153. Users by survey

---

## Category 3: Form Elements & Validation (23 strings)

Form fields, inputs, validation, slugs, and configuration options.

1. Choose your preferred language. This affects all text in the application.
2. Choose your theme. This only affects your view and is saved in your browser.
3. URL Name or 'Slug' (optional)
4. Optional: Follow-up text inputs
5. Add a follow-up text input to any option by adding an indented line starting \nwith <code>+</code>
6. The text after <code>+</code> becomes the label for the follow-up input field
7. Follow-up lines must start with <code>+</code> and be indented (at least 2 \nspaces)
8. For Likert scales, provide <code>min</code>/<code>max</code> and optional \nlabels
9. select menu
10. (optional)
11. Create repeat
12. Nest under existing (optional)
13. Nesting is limited to one level (Parent → Child) by design.
14. Note: In the preview below, a repeat card will only show if there is at least one group marked as repeatable in this survey. You can test adding/removing instances.
15. Importing from Markdown will delete all existing question groups, questions, \nbranching rules, and repeats. This action cannot be undone.
16. Optional: Follow-up text inputs (dropdown, mc_single, mc_multi, yesno)
17. For <code>yesno</code>, provide exactly 2 options (Yes/No) with optional \nfollow-ups
18. Operators mirror the survey builder: <code>equals</code>, <code>not_equals</code>, <code>contains</code>, <code>not_contains</code>, <code>greater_than</code>, <code>less_than</code>
19. Point to a group ID to jump to that group, or a question ID to jump directly \nto that question
20. Assign stable IDs by placing them in curly braces at the end of group or \nquestion titles
21. IDs are normalised to lowercase slugs; keep them unique within your document.
22. If the type requires options, list each on a line starting with <code>-</code>
23. <code>(type)</code> on the next line in parentheses

---

## Category 4: UI Components & Navigation (16 strings)

Buttons, links, navigation elements, and UI controls.

1. Organisation created. You are an organisation admin.
2. Analyze
3. CheckTick
4. Home
5. Distribute
6. Explore docs
7. See capabilities
8. Live structure preview
9. Preview (read-only)
10. Public link
11. Unlisted link
12. Preview
13. Request a new link
14. Send reset link
15. Create an organisation to collaborate with a team
16. Create surveys and manage your own responses

---

## Category 5: Documentation & Help Text (8 strings)

Long-form help text, documentation, and explanatory content.

1. <strong>REPEAT</strong> = unlimited repeats. <strong>REPEAT-1</strong> means \nonly 1 allowed, <strong>REPEAT-1-5</strong> allows 1 to 5.
2. Not all options need follow-ups—only add them where needed
3. <strong>Groups</strong> are reusable sets of questions. You can mark one or \nmore groups as a <strong>repeat</strong> (collection), allowing users to add \nmultiple instances of those groups when filling out the survey.
4. Use markdown with the following structure:
5. Supported types
6. categories listed with <code>-</code>
7. Organisation names don't need to be unique. Multiple organisations can have \nthe same name—you'll only see and manage your own.
8. Format reference

---

## Category 6: General UI Text (89 strings)

Labels, headings, status messages, badges, settings, and general interface text

1. Your Profile
2. Your badges
3. Language preference updated successfully.
4. There was an error updating your language preference.
5. Project theme saved.
6. You have staff-level access to the platform
7. You have full administrative access to the platform
8. Appearance
9. Language
10. Save Language Preference
11. Theme
12. Light
13. Dark
14. Enable JavaScript to change theme.
15. Window
16. Today
17. Last 7 days
18. Last 14 days
19. Closed
20. Authenticated
21. Public
22. Unlisted
23. Start at
24. End at
25. Danger Zone
26. Warning: This action cannot be undone!
27. Yes
28. No
29. Professional details
30. Submit
31. Repeats
32. Remove repeat
33. Clear
34. Help
35. Repeat name
36. Minimum items
37. Maximum items
38. Unlimited
39. Nesting is limited to one level.
40. Import
41. Organisation users
42. How many
43. Expires at (ISO)
44. Generate
45. Export CSV
46. Expires
47. Used
48. Used by
49. User management
50. You don't have an organisation to manage yet.
51. Organisation
52. Add user to org
53. No users yet
54. No members
55. Please correct the error below.
56. Built by
57. GitHub
58. Issues
59. Releases
60. Contributing
61. Version
62. Branch
63. Commit
64. Individual User
65. Organisation Name
66. e.g. Acme Health Research
67. Leave blank to use default name
68. Note:
69. Markdown
70. Add <code class=\"required\"</code> to mark a question as required
71. The asterisk <code class=\"required\"</code> method is recommended for \nsimplicity
72. free text
73. numeric input
74. multiple choice (single)
75. multiple choice (multi)
76. orderable list
77. image choice
78. yes/no
79. Draft
80. Published
81. For options that should have follow-up text input, add an indented line \nstarting with <code>+</code> followed by the label text
82. Works with <code>mc_single</code>, <code>mc_multi</code>, <code>dropdown</code>, and <code>yesno</code> question types
83. Published: ready to accept responses.
84. Open the survey in a new window to invite participants.
85. What's this?
86. Visibility
87. Authenticated: participants must log in before accessing. Public: anyone with \nthe link. Unlisted: secret link, no directory listing.
88. For public/unlisted surveys, all form fields (name, email, etc.) are \nautomatically encrypted—unless you explicitly opt out of encryption for a given \nquestion. The survey will prompt for a one-time decryption key on dashboard load.
89. Submissions
