import json
import openreview
import tqdm
import collections

from genderize import Genderize

# Change these values according to your needs
INVITATIONS ={
  "2017": 'ICLR.cc/2017/conference/-/submission',
  "2018": 'ICLR.cc/2018/Conference/-/Blind_Submission',
}

GENDER_MAP = {
"male": ["Male", "male", "M"],
"female": ["Female", "female"],
"all_other_genders": ["Non-Binary"],
"needs_prediction": ["Unspecified", "Not Specified"]
}

def categorize_gender(gender):
  for general, variations in GENDER_MAP.items():
    if gender in variations:
      return general
  assert False


# A client is required for any OpenReview API actions
guest_client = openreview.Client(baseurl='https://api.openreview.net')


author_pool = set()

for year, invitation in INVITATIONS.items():
  for i, forum_note in tqdm.tqdm(enumerate(openreview.tools.iterget_notes(
        guest_client, invitation=invitation))):
    authors = forum_note.content['authors']
    if type(authors) == str:
      assert 'authorids' not in forum_note.content
      author_ids = [forum_note.content['author_emails']]
    else:
      author_ids = forum_note.content['authorids']
    author_pool.update(author_ids)


gender_collector = collections.Counter()


class Author(object):
  def __init__(self, profile, author_id):
    self.profile = profile
    self.author_id = author_id
    self.first, self.middle, self.last = self._get_preferred_name()
    self.gender = None
    if 'gender' in profile.content:
      maybe_gender = profile.content['gender']
      if maybe_gender is not None and maybe_gender.strip():
        self.gender = maybe_gender
        self.gender_category = categorize_gender(maybe_gender)
    if self.gender is None:
      self.genderize_output = Genderize().get([self.first])[0]
      if self.genderize_output['probability'] < 0.95:
        self.gender_category = "gz|low_conf"
      else:
        self.gender_category = f"gz|{self.genderize_output['gender']}"
    print(self.gender_category)

  def _get_preferred_name(self):
    preferred_name = None
    for name_dict in self.profile.content['names']:
      if 'preferred' in name_dict and name_dict['preferred']:
        preferred_name = name_dict
        break
    if preferred_name is None:
      preferred_name = self.profile.content['names'][0]
    return [preferred_name[k] for k in "first middle last".split()]

  def to_dict(self):
    return {
      "first": self.first,
      "middle": self.middle,
      "last": self.last,
      "author_id": self.author_id,
      "gender": self.gender,
      "gender_category": self.gender_category
    }

sorted_author_ids = sorted(author_pool)
authors = {}
for i, author_id in enumerate(tqdm.tqdm(sorted_author_ids)):
  try:
    maybe_profile = guest_client.get_profile(author_id)
    authors[author_id] = Author(maybe_profile, author_id)
  except openreview.OpenReviewException:
    pass

with open('author_gender.json', 'w') as f:
  json.dump([a.to_dict() for a in authors.values()], f)
