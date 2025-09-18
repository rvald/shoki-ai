from deepeval import evaluate
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.metrics import GEval

input = "Hi <PERSON>, it’s good to see you again. How have you been feeling since our last session on <DATE_TIME>? Hi, Doc. I’ve been feeling a lot better overall. I’ve been using the coping strategies we talked about, and I’ve started doing things I used to enjoy. My mood has definitely improved, and the depressive symptoms aren’t as bad or as frequent. That’s great to hear. Do you want to share any specific experiences that helped with your mood? Yes, I recently went to a family gathering at my brother's house on <ADDRESS>. My sister <PERSON> was visiting from out of town. It was wonderful! I felt really connected and engaged with everyone there. It gave me a good sense of support, which helped a lot. My son <PERSON> took photos—I'll forward them to you at <EMAIL_ADDRESS>, if that's okay. I’m glad you had that positive experience. Have you noticed any other changes, such as your energy levels or activity? Yeah, I’ve been more active—walking and jogging regularly with my neighbor <PERSON>—and I feel more energetic. Excellent progress, <PERSON>. How about your sleep? Any changes there? That’s still a bit of a problem. Sometimes I have trouble falling asleep, and I wake up earlier than I want to, usually <DATE_TIME> Thanks for letting me know. Just to confirm, is your current insurance still under Blue Cross Plan ID <DATE_TIME>? Yes, that's right. And if you need to reach me, my cell is <PHONE_NUMBER> and my work email is <EMAIL_ADDRESS>. We’ll continue reinforcing your coping strategies and start focusing more on your sleep—looking at triggers and teaching you relaxation and sleep hygiene techniques. Sounds good. My birthday's coming up on <DATE_TIME>, so I’m hoping to celebrate feeling better. You’re doing really well. Keep up the good work, and we’ll keep working on these areas next time. See you soon!Thanks, Doc. See you soon!"
output = """{"hippa_compliant" : true}"""
expected_output = """{"hippa_compliant" : true}"""

# Define the evaluation metric
correctness_metric = GEval(
    name="Correctness",
    criteria="Determine if the 'actual output' is correct based on the 'expected output'.",
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    threshold=0.5
)

# Create a test case
test_case = LLMTestCase(
    input=input,
    # Replace this with the actual output from your LLM application
    actual_output=output,
    expected_output=expected_output
)

# Run the evaluation
evaluate([test_case], [correctness_metric])