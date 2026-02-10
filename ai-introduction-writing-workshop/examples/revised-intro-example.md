The academic performance of students is one of the integral 
mechanisms for evaluating an academic institution. It also helps 
design operative instruments that improve students’ academic outcomes and avoid dropout, among other things. For example, 
West African second-cycle schools are usually ranked yearly 
based on the general performance of their students in the West 
African Examination Council (WAEC). Likewise, in Ghana, 
the rank of basic educational (primary and junior secondary 
schools) institutions is partially based on their students’ 
performance in the Basic Education Certificate Examination 
(BECE). Therefore, a means to correctly articulate students’ 
academic performance before their final examination at all 
education levels is critical to all academic institutions. 
Recently, there has been a decline in the general performance 
of students in science, mathematics and information 
technology. Some nationalists blame the use of foreign 
languages for teaching as responsible for poor academic 
performance and even underdevelopment among students [1].
However, other studies [2]–[5] have argued that students’ 
academic performance goes beyond the language for means of 
instruction; it fundamentally includes both cognitive (such as 
high school grade point average) and non-cognitive 
characteristics. The non-cognitive characteristics include 
student engagement, behavioural observations at school, the 
general views of family and friends concerning schooling, 
gender, place of birth and involvement in extracurricular 
activities.
Recently, advancement in technology has resulted in a large 
amount of collected cognitive and non-cognitive educational 
data. Nevertheless, analysing big data to reach insightful 
information is challenging for humanity using traditional 
techniques [6]. However, Data Mining (DM) methods can be 
used effectively to learn treasured and essential hidden 
knowledge from these data. Thus, Educational Data Mining 
(EDM), i.e., analysing data of educational institutions with DM 
methods, is valuable for dramatically improving students’ 
academic performance. Educational Data Mining implements 
data mining methods for analysing available data at educational 
institutions [6]. Although EDM leads to knowledge discovery, Machine Learning Algorithms (MLAs) provide the needed 
tools for this purpose. Hence, critical analysis and processing of 
educational data with MLAs can lead to valuable statistics 
concerning students’ knowledge, association and academic 
performance.
This paper seeks to examine the degree to which cognitive
and non-cognitive characteristics influence the academic 
performance of students at second-cycle schools using MLAs, 
as well as compares and evaluates the predictive performance 
of different classification methods for predicting students’ 
academic performance. Specifically, we seek to:
i. Examine which factors, cognitive or non-cognitive or 
both, are significant predictors of students’ academic 
performance.
ii. Perform a comparative analysis of different MLAs for 
predicting student academic performance to identify 
which algorithm improves prediction accuracy.
iii. Predict the average grade score of a student in 
mathematics, science and information technology and 
estimate whether a student is at risk of failing the final 
examination based on the best classification algorithm 
from the comparative analysis.
iv. Examine the effect of k-fold and leave-one-out crossvalidation training techniques on the prediction 
accuracy of different MLAs for predicting students’ 
academic performance.
The following research questions have been formulated:
RQ1: Which MLAs are appropriate for effective and 
efficient prediction of students’ academic performance?
RQ2: Which cognitive and non-cognitive factors affect 
students’ academic performance and predictive performance of 
MLAs?
We hope that the outcome of this study will help identify: (i) 
different cognitive and non-cognitive factors that significantly 
influence students’ academic performance; (ii) a training 
technique (i.e., k-fold cross-validation or leave-one-out) that is 
more suitable for training MLAs to predict students’ academic 
performance; (iii) the appropriate MLAs for predicting 
students’ academic performance and determine the best 
approach for performing student performance prediction. This 
paper uses various machine learning classifiers, including 
Decision Tree (DT), K-Nearest-Neighbour (KNN), Artificial 
Neural Network (ANN), Logistic Regression (LR), Random 
Forest (RF), AdaBoost and Support Vector Machine (Radial 
Basis Function). These techniques have been chosen for this 
study based on their straightforward implementation and 
efficiency in classification tasks in different fields, such as 
engineering [7]–[10], finance [11]–[14] and education [15]–
[18].

The rest of the paper is structured as follows: Section 2 
presents review of literature. Section 3 presents the study 
methodology. Then, the study results are considered in 
Section 4, while conclusions and future research areas are 
discussed in Section 5.
