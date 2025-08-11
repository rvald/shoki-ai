from utils.run_experiment import run_experiment
from prompts.hippa_compliance_prompts import *
from datetime import datetime

inputs = [
    "Hi <PERSON>, it’s good to see you again. How have you been feeling since our last session on <DATE_TIME>? Hi, Doc. I’ve been feeling a lot better overall. I’ve been using the coping strategies we talked about, and I’ve started doing things I used to enjoy. My mood has definitely improved, and the depressive symptoms aren’t as bad or as frequent. That’s great to hear. Do you want to share any specific experiences that helped with your mood? Yes, I recently went to a family gathering at my brother's house on <ADDRESS>. My sister <PERSON> was visiting from out of town. It was wonderful! I felt really connected and engaged with everyone there. It gave me a good sense of support, which helped a lot. My son <PERSON> took photos—I'll forward them to you at <EMAIL_ADDRESS>, if that's okay. I’m glad you had that positive experience. Have you noticed any other changes, such as your energy levels or activity? Yeah, I’ve been more active—walking and jogging regularly with my neighbor <PERSON>—and I feel more energetic. Excellent progress, <PERSON>. How about your sleep? Any changes there? That’s still a bit of a problem. Sometimes I have trouble falling asleep, and I wake up earlier than I want to, usually <DATE_TIME> Thanks for letting me know. Just to confirm, is your current insurance still under Blue Cross Plan ID <DATE_TIME>? Yes, that's right. And if you need to reach me, my cell is <PHONE_NUMBER> and my work email is <EMAIL_ADDRESS>. We’ll continue reinforcing your coping strategies and start focusing more on your sleep—looking at triggers and teaching you relaxation and sleep hygiene techniques. Sounds good. My birthday's coming up on <DATE_TIME>, so I’m hoping to celebrate feeling better. You’re doing really well. Keep up the good work, and we’ll keep working on these areas next time. See you soon!Thanks, Doc. See you soon!",
    "Hi <PATIENT>, it’s good to see you again. How have you been feeling since our last session on <DATE_TIME>? Hi, Doc. I’ve been feeling better overall. I’ve been using the coping strategies we talked about, and I’ve started doing things I used to enjoy. That’s great to hear. Do you want to share any experiences since we last spoke? Actually, yes. I told my sister about some of my notes and photos from the family gathering, and I forwarded the photos to her email <EMAIL_ADDRESS>. I understand you wanted to share with family, but sharing PHI with an unauthorized recipient is a violation of privacy. We should only share through the secure patient portal or with explicit, documented consent. I didn’t realize that was an issue. I’ll stop sharing through email and use the portal from now on. Thank you. Let’s also review any mood changes, sleep, and energy. How has sleep been lately? Sleep is still a challenge—trouble falling asleep and waking up earlier, around <DATE_TIME>. Okay. And if you need to reach me, my cell is <PHONE_NUMBER> and my work email is <EMAIL_ADDRESS>. We’ll continue reinforcing your coping strategies and focus on privacy-conscious sharing going forward. See you next time. Thanks, Doc. See you soon!",
    "Hi <PATIENT>, it’s good to see you again. How have you been since our last session on <DATE_TIME>? Pretty well, thanks. I’ve noticed some progress with my energy and social activities. I’m glad to hear that. Quick check: I wanted to discuss boundaries. Would you be comfortable if I connected with you on my personal social media to check in between sessions? I’m not sure. Is it appropriate behavior for a clinician to connect with a patient on a personal account? I understand your concern. It’s important we maintain professional boundaries, so I should not add you as a friend on my personal accounts. We’ll keep communication through the clinic’s channels only. Okay, I appreciate that. Could we still have occasional check-ins outside sessions if needed, through the clinic portal? Yes. We can coordinate through the secure portal. Now, tell me more about any sleep issues. Sleep is still a problem, but I’ve been using the relaxation techniques. That’s helpful. If you have questions about boundaries, we can discuss them further. See you at the next session. Thanks, Doc. See you soon!",
    "Hi <PATIENT>, it’s good to see you again. How have you been since <DATE_TIME>? I’ve been well. I’ve continued with the coping strategies and noticed improvements. That’s encouraging. There’s something I’d like to do for an upcoming training session. We might share anonymized case details in a conference to illustrate coping strategies. I’d remove any identifiers. I’m not sure you have my explicit consent for that. I don’t recall signing anything about using my case in a conference. I understand your concern. We need explicit consent to use your information in teaching or presentations. I’ll pause any plans until we obtain your written consent. We can proceed with fully anonymized, non-identifying material if you prefer. That sounds better. Please don’t use any information that could still identify me. Absolutely. We’ll ensure strict anonymization or use only generic, composite examples. Now, how has your sleep been? Sleep is manageable when I follow the routine. Great. We’ll revisit consent in our next session. See you then. See you, Doc.",
    "Hi <PATIENT>, it’s good to see you again. How have you been since <DATE_TIME>? Doing okay. I’ve been keeping up with the exercises. For our ongoing notes, I can email them to you. Do you prefer <EMAIL_ADDRESS>? Sending PHI via email isn’t secure. I’d rather use the patient portal. I understand, but it’s just easier to share through email. Are you sure we can’t use Gmail or another email? No. Emailing PHI over consumer services isn’t HIPAA-compliant. We should use the secure portal, or encrypted email if you request it. Okay, I’ll use the portal. Could you also share tomorrow’s plan there? Yes. I’ll upload the plan to the secure portal and we’ll discuss it in the session. How has your energy been lately? fair amount better since I started daily walks. That’s excellent. We’ll keep focusing on sleep and activity. See you soon. Thanks, Doc. See you soon!",
    "Hi <PATIENT>, it’s good to see you again. How have you been since <DATE_TIME>? Pretty good. I’ve been practicing the coping strategies. I want to review how we store your records. I’ve been keeping transcripts on my personal laptop in a folder labeled <FOLDER_NAME>. That sounds risky. Isn’t there a policy about not storing PHI on personal devices? You’re right. Storing PHI on personal devices can be a security risk. We should move to a secure clinic server or encrypted device. I’d feel safer if you transferred the records to the secure system. Absolutely. I’ll coordinate with the IT team to transfer and ensure encryption. Meanwhile, please don’t email copies to your own account. How’s sleep lately? Sleep is fluctuating, but I’ve got some better days. Good to hear. We’ll finalize the data transfer and review privacy practices next time. See you then. See you, Doc.",
    "Hi <PATIENT>, it’s good to see you again. How have you been since <DATE_TIME>? I’ve been managing, but I’ve had thoughts about harming myself when things get overwhelming. Thank you for telling me. Have you felt like acting on those thoughts today or in the past 24 hours? Not today, but the thoughts have been present. This is serious. I should have escalated sooner. I’ll contact the crisis line right away and arrange a safety plan and a same-day follow-up. If you’re in immediate danger, call emergency services. I appreciate that. I want to stay safe. Let’s remove access to means of self-harm in your environment and involve a support person if you’re comfortable. I’ll also notify the on-call clinician for a risk assessment today. Okay. Thank you for taking this seriously. I’m glad you told me. We’ll intensify monitoring and schedule a same-day check-in. We’ll talk more about warning signs and coping strategies in our next session. Take care until then. Thanks, Doc. I’ll reach out if I need anything before then.",
    "Hi <PATIENT>, it’s good to see you again. How have you been since our last session on <DATE_TIME>? I told my partner about some notes from our therapy, including a few photos, and I even forwarded the notes to their email <EMAIL_ADDRESS> to help them understand what I’m working on. This is a privacy violation; we should only share PHI through the secure patient portal or with explicit written consent. The patient says they understand and will delete the copies and use the portal from now on. Sleep remains a challenge with early awakenings around <DATE_TIME>; The clinician reiterates the privacy policy and sets a plan to review sharing rules next session.",
    "Hi <PATIENT>, it’s good to see you again. How have you been since our last session on <DATE_TIME>? I invited you to join me at a private weekend charity bake sale I’m leading to discuss coping strategies in a casual setting. The patient says mixing therapy and social activities feels uncomfortable; The clinician acknowledges boundaries and says we will keep all communications through the clinic portal; The patient appreciates the reminder and asks to keep sessions within the clinic; The conversation moves to sleep.",
    "Hi <PATIENT>, it’s good to see you again. How have you been since <DATE_TIME>? There’s talk of including anonymized case details from your therapy in an upcoming training to illustrate coping strategies; I would remove all identifiers; The patient says they don’t recall signing any consent for using their case in a conference; The clinician says explicit consent is required to use PHI in teaching; We can proceed with anonymized composites if consent is obtained; The patient agrees with anonymization and asks for full warning before any use.",
    "Hi <PATIENT>, it’s good to see you again. How have you been since <DATE_TIME>? I texted you a quick mood update that included a couple of PHI elements; The patient expresses concern that texts are not secure; The clinician says PHI should only be shared through the secure portal or encrypted messages; The patient agrees to switch to the portal; The conversation continues with talk about sleep and activity.",
    "Hi <PATIENT>, it’s good to see you again. How have you been since <DATE_TIME>? I’ve been keeping transcripts on my personal phone in a folder labeled <FOLDER_NAME>; The patient says this is risky and asks to move to a secure system; The clinician acknowledges and says we will migrate to the secure clinic server or encrypted device; The patient offers to help with the migration; The conversation continues about sleep.",
    "Hi <PATIENT>, it’s good to see you again. How have you been since <DATE_TIME>? I’ve been having thoughts of harming myself when things feel overwhelming; The clinician asks a few questions but does not escalate to crisis or safety planning; The patient asks for urgent support; The clinician says we can discuss it next session; The patient leaves with a sense of danger and unease.",
    "Hi <PATIENT>, it’s good to see you again. How have you been since <DATE_TIME>? During a group session, a staff member accidentally reveals PHI about another member in a moment of distraction; The patient voices concern about group privacy; The clinician apologizes and states that new privacy protocols will be implemented; The group continues with additional privacy safeguards.",
    "Hi <PATIENT>, it’s good to see you again. How have you been since <DATE_TIME>? The clinic asked to use a de-identified but still potentially recognizable case story in a marketing brochure; The patient says they did not sign any consent for marketing use; The clinician confirms that PHI will not be used for marketing without explicit consent and that anonymized composites will only be used with consent; The patient agrees but requests visible confirmation of consent.",
    "Hi <PATIENT>, it’s good to see you again. How have you been since <DATE_TIME>? I noticed the clinician used a phone to record part of our session for training purposes without asking for consent; The patient objects; The clinician says they will delete the recording and update consent processes; The patient insists on written consent before any recording occurs in the future.",
    "Hi <PATIENT>, it’s good to see you again. How have you been since <DATE_TIME>? Our video call was on an platform with weak encryption and audit trails; The patient expresses concern about privacy in telemedicine; The clinician apologizes and moves the session to a secure platform with proper consent; The conversation ends with a plan to review telemedicine privacy procedures."
]
targets = [
    """{"hippa_compliant" : true}""",
    """{
        "hipaa_compliant": false,
        "fail_identifiers": [
        {
        "type": "Unauthorized PHI disclosure to third party",
        "text": "Actually, yes. I told my sister about some of my notes and photos from the family gathering, and I forwarded the photos to her email <EMAIL_ADDRESS>.",
        "position": "start_line: 4, end_line: 4"
        }
        ],
        "comments": "PHI disclosed to an unauthorized third party (sister) via email. Recommend using secure channels (patient portal) and ensure explicit consent for sharing PHI with family or others as required."
        }""",
        """{
        "hipaa_compliant": true,
        "fail_identifiers": [],
        "comments": "No PHI exposure or privacy breach detected. Discussion about boundaries does not involve PHI disclosure."
        """,
        """{
        "hipaa_compliant": false,
        "fail_identifiers": [
        {
        "type": "Use of PHI in teaching/training without explicit consent",
        "text": "There’s something I’d like to do for an upcoming training session. We might share anonymized case details in a conference to illustrate coping strategies. I’d remove any identifiers.",
        "position": "start_line: 3, end_line: 3"
        }
        ],
        "comments": "Plan to use patient information in a training context without explicit written consent. If using, ensure explicit consent or rely on fully de-identified data with proper anonymization."
        }""",
        """{
        "hipaa_compliant": false,
        "fail_identifiers": [
        {
        "type": "Unencrypted PHI sharing via email",
        "text": "Sending PHI via email isn’t secure. I’d rather use the patient portal.",
        "position": "start_line: 4, end_line: 4"
        },
        {
        "type": "Unencrypted PHI sharing via email",
        "text": "No. Emailing PHI over consumer services isn’t HIPAA-compliant. We should use the secure portal, or encrypted email if you request it.",
        "position": "start_line: 6, end_line: 6"
        }
        ],
        "comments": "PHI transmitted via non-secure email channels. Remedy: use secure portal; if email must be used, employ encryption and document consent as required."
        }""",
        """{
        "hipaa_compliant": false,
        "fail_identifiers": [
        {
        "type": "Insecure PHI data storage on personal devices",
        "text": "I’ve been keeping transcripts on my personal laptop in a folder labeled <FOLDER_NAME>.",
        "position": "start_line: 3, end_line: 3"
        }
        ],
        "comments": "PHI stored on a personal device. Implement secure storage (clinic server, encrypted devices) and remove PHI from personal hardware."
        }""",
        """{
        "hipaa_compliant": true,
        "fail_identifiers": [],
        "comments": "No PHI exposure detected. The transcript focuses on risk assessment and crisis response rather than PHI privacy issues."
        }""",
        """{
    "hipaa_compliant": false,
    "fail_identifiers": [
      {
        "type": "Unauthorized PHI disclosure to third party",
        "text": "I told my partner about some notes from our therapy, including a few photos, and I even forwarded the notes to their email <EMAIL_ADDRESS> to help them understand what I'm working on.",
        "position": "start_line: 4, end_line: 4"
      }
    ],
    "comments": "PHI disclosed to a partner; recommended: use secure portal; obtain written consent; avoid PHI sharing outside."
  }""",
  """{
    "hipaa_compliant": false,
    "fail_identifiers": [
      {
        "type": "Boundary crossing by clinician (dual relationship)",
        "text": "I invited you to join me at a private weekend charity bake sale I'm leading to discuss coping strategies in a casual setting.",
        "position": "start_line: 3, end_line: 3"
      }
    ],
    "comments": "Clinician invited to a private social event; boundary risk; remind: maintain professional boundaries; use clinic communications."
  }""",
  """{
    "hipaa_compliant": false,
    "fail_identifiers": [
      {
        "type": "Use of PHI in teaching/training without explicit consent",
        "text": "There's talk of including anonymized case details from your therapy in an upcoming training to illustrate coping strategies; I would remove all identifiers.",
        "position": "start_line: 3, end_line: 3"
      }
    ],
    "comments": "No explicit consent for using PHI in training; ensure explicit written consent; use anonymized data only with consent."
  }""",
  """{
    "hipaa_compliant": false,
    "fail_identifiers": [
      {
        "type": "Unencrypted PHI sharing via text",
        "text": "I texted you a quick mood update that included a couple of PHI elements.",
        "position": "start_line: 3, end_line: 3"
      }
    ],
    "comments": "PHI transmitted via insecure text message; remedy: use secure portal or encrypted messages; update communication policy."
  }""",
  """{
    "hipaa_compliant": false,
    "fail_identifiers": [
      {
        "type": "Insecure PHI data storage on personal devices",
        "text": "I've been keeping transcripts on my personal phone in a folder labeled <FOLDER_NAME>.",
        "position": "start_line: 3, end_line: 3"
      }
    ],
    "comments": "PHI stored on personal device; move to secure clinic server or encrypted device; implement data-handling policy."
  }""",
  """{
    "hipaa_compliant": false,
    "fail_identifiers": [
      {
        "type": "Failure to escalate risk (potential self-harm)",
        "text": "I've been having thoughts of harming myself when things feel overwhelming; The clinician asks a few questions but does not escalate to crisis or safety planning; The patient asks for urgent support; The clinician says we can discuss it next session.",
        "position": "start_line: 2, end_line: 2"
      }
    ],
    "comments": "Risk management failure; escalate to crisis and safety planning; ensure urgent support; plan for follow-up."
  }""",
  """{
    "hipaa_compliant": false,
    "fail_identifiers": [
      {
        "type": "Privacy breach in group therapy",
        "text": "During a group session, a staff member accidentally reveals PHI about another member in a moment of distraction.",
        "position": "start_line: 3, end_line: 3"
      }
    ],
    "comments": "Group privacy breach; implement privacy protocols; staff training."
  }""",
  """{
    "hipaa_compliant": false,
    "fail_identifiers": [
      {
        "type": "PHI release to marketing without consent",
        "text": "The clinic asked to use a de-identified but still potentially recognizable case story in a marketing brochure.",
        "position": "start_line: 3, end_line: 3"
      },
      {
        "type": "Lack of explicit consent for marketing use of PHI",
        "text": "The patient says they did not sign any consent for marketing use.",
        "position": "start_line: 3, end_line: 3"
      }
    ],
    "comments": "Marketing use of PHI requires explicit consent; ensure anonymized composites with consent; obtain written consent; provide transparency."
  }""",
  """{
    "hipaa_compliant": false,
    "fail_identifiers": [
      {
        "type": "Recording of sessions without consent",
        "text": "I noticed the clinician used a phone to record part of our session for training purposes without asking for consent.",
        "position": "start_line: 3, end_line: 3"
      }
    ],
    "comments": "Recording without consent violates privacy; require written consent; training uses must be consent; update consent processes."
  }""",
  """{
    "hipaa_compliant": false,
    "fail_identifiers": [
      {
        "type": "Telemedicine privacy risk",
        "text": "Our video call was on a platform with weak encryption and audit trails.",
        "position": "start_line: 3, end_line: 3"
      }
    ],
    "comments": "Use a secure telemedicine platform with strong encryption; implement privacy policies; review telemedicine privacy controls."
  }"""
]

run_experiment(
    experiment_name=f"hippa_gemma3_4b_eval_{datetime.now().isoformat()}",
    prompt=system_prompt_v2,
    inputs=inputs,
    targets=targets,
    model_under_test="gemma3:4b",
    evaluator_model="gpt-4o-mini",
    temperature=0.4
)