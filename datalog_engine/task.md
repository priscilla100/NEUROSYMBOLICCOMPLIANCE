I have given you a PDF file "HIPAA_FORMALIZATION.pdf" which formalizes HIPAA in first-order temporal logic.
Read the full PDF first and carefully. The formalization can be found in page ranges 30-122. The formalization particularly 
focuses on the HIPAA privacy rule. I want you to convert the formalization they used 
including macros, constraints, and positive, and negative rules/norms into datalog. Here 
is the requirement. You will have a facts DB with the necessary facts. Since Souffle doesn't 
support temporal logic natively you will use Kamp-style translation to first order logic, and 
then the Souffle language. The top level rule will be called: Is_disclosure_allowed(p1, p2, q, m, t, u) where 
p1 is the sender, p2 is the receiver, t is the attribute shared in the message m about principal q for the 
purpose u. You will essentially create a compliance checker. Try to be faithful. One of the thing 
I would like is that you use explanation using Datalog of why certain disclosure is allowed. For that 
you will use ADTs in the form shown in the convo_summary.md file, which is given to you. Every rule you 
convert please make sure another agent verifies it. Make sure the syntax of the souffle file you generate 
is correct and compiles ok. Also generate some fictitious scenarios and generate its fact DB to make sure 
we can test it. Also make sure the fact DB is in a different file if possible. Again verification is main. 
For provenance, use the text in the PDF file I gave you "HIPAA_FORMALIZATION.pdf" for verification. Add much 
comments as you can. Please make sure you work in token-optimization way and use sub-agents to speed up the 
process and do things in parallel. First formalize 164.502 and 164.506 sections. Once you have received verification 
from me, only then start formalizing the rest. Please make sure "constraints" and "macros" are also captured in a fine-grained 
fashion, not just disclosure rules. Also, capture role hierarchy and attribute hierarchy. The current formalization does 
not include purpose. Include it whenever relevant. 

If you have to install a Python package, then do not break the system installation and rather do a virtual environment 
with requirement.txt file (or something idiomatic) to install that package. Again do not break my system-wide python. 

## Testing Strategy

Follow the following testing strategy to test your formalization. 

Use 30 test cases. 

(1) You come up with a fictitious scenario; 
(2) You go up the Internet and find out whether a disclosure will be allowed by HIPAA on the fictitious scenario; 
(3) Encode the scenario as facts and a new query
(4) Run your datalog encoding and obtain a result
(5) Whatever the datalog gives you and what you independently obtained by analyzing the HIPAA regulation, see whether it matches. 
(6) If it matches, then this test case passes. 
(7) If it does not match, either the formalization is wrong or your adjudication is wrong. 
(8) If the formalization is wrong, update it. 
(9) If your adjudication is wrong, then save the test case in a file called "CLAUDE_FAILED_TEST_CASES.md" 

Follow the above testing strategy for 30 use-cases. 
You can use the dataset from the "https://github.com/HKUST-KnowComp/GoldCoin"
Note that, the current formalization covers some part only. As a result the formalization may end up failing. Also 
store such formalization error test cases in a file called "FORMALIZATION_FAILED_TEST_CASES.md"

Finally, go over the PDF "HIPAA_FORMALIZATION.pdf" with a fine-tooth comb and see whether there are mismatches. Fix them 
if there are issues in the formalization. 

Please make sure all the test cases are stored. 

Two things: (1) For the test cases you have already run, please store them in a folder called "CLAUDE_GENERATED_TEST_CASES" (you will keep updating this
  file); (2) I have updated task.md to include testing strategy. Use the testing strategy to test the formalization.