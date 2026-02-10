# I. INTRODUCTION
The evaluation of academic institutions is often thought to be related to student performance, which is a metric that might be considered important by various stakeholders. It is possible that by studying these outcomes, one could perhaps design instruments to slightly improve student results or maybe reduce dropout rates. In certain regions, such as West Africa, schools are sometimes ranked based on WAEC results, and a similar situation appears to exist in Ghana regarding the BECE. Therefore, it might be somewhat useful to find a way to talk about academic performance before exams actually happen, although this is quite a complex task.

Recently, there has been a perceived decline in subjects like science and math. Some people suggest that teaching in foreign languages is the main problem [1]. However, it is also argued by others [2]–[5] that there are probably many other factors involved. These might include cognitive things, like GPA, or non-cognitive things, such as whether a student likes school, their gender, or if they do sports. Because we now have a lot of computers, we have a lot of data on these things.

Traditional ways of looking at this data are sometimes difficult for people [6]. Data Mining (DM) is a thing that can be used to look for hidden patterns. When you do this in education, it is called Educational Data Mining (EDM). This paper basically tries to use Machine Learning Algorithms (MLAs) because they are tools that exist for discovery. We think that processing this data might lead to some statistics that could be valuable for someone.

This paper just wants to see how much these factors matter using some MLAs. We also plan to compare some different classification methods to see which one is better at guessing. Specifically, we will try to:

Look at whether cognitive or non-cognitive factors (or both) seem to predict things.

Do a comparison of some MLAs to see if any of them are more accurate than the others.

Try to guess the average grades in a few subjects and see if a student might fail.

Look at two different training techniques, k-fold and leave-one-out, just to see what happens to the accuracy.

We have two general research questions:

RQ1: Which MLAs are okay to use for predicting performance?

RQ2: Which factors seem to affect the results?

We hope that maybe this study will help identify some factors or techniques that are suitable. This paper uses a variety of common classifiers like Decision Trees, KNN, and others. These were picked because they are relatively easy to do and have been used in other fields like finance and engineering [7]–[18].

The rest of the paper follows a standard format: Section 2 is the literature, Section 3 is what we did, Section 4 is what we found, and Section 5 is the end.
The rest of the paper is structured as follows: Section 2 
presents review of literature. Section 3 presents the study 
methodology. Then, the study results are considered in 
Section 4, while conclusions and future research areas are 
discussed in Section 5.

## Refrences:
[1] E. I. Ani, “Debating the roots of poor academic performance in the West 
African subregion: The perspective of a philosopher,” SAGE Open, vol. 7, 
no. 2, Art no. 2158244017707795, May 2017. 
https://doi.org/10.1177/2158244017707795
[2] B. G. Adams, N. Wiium, and A. Abubakar, “Developmental assets and 
academic performance of adolescents in Ghana, Kenya, and South 
Africa,” Child & Youth Care Forum, vol. 48, no. 2, pp. 207–222, Nov. 
2019. https://doi.org/10.1007/s10566-018-9480-z
[3] S. Venkatesh, Y. K. Rao, H. Nagaraja, T. Woolley, F. O. Alele, and 
B. S. Malau-Aduli, “Factors influencing medical students’ experiences 
and satisfaction with blended integrated e-learning,” Medical Principles 
and Practice, vol. 29, no. 4, pp. 396–402, Jul. 2020. 
https://doi.org/10.1159/000505210
[4] L. F. Casinillo, M. A. E. Palen, E. L. Casinillo, and P. G. Batidor, 
“Assessing senior high student’s learning experiences in mathematics,”
Indonesian Journal of Educational Studies, vol. 23, no. 1, pp. 44–60, 
2020. https://doi.org/10.26858/ijes.v23i1.13437
[5] C. Semeraro, D. Giofrè, G. Coppola, D. Lucangeli, and R. Cassibba, “The 
role of cognitive and non-cognitive factors in mathematics achievement: 
The importance of the quality of the student-teacher relationship in middle 
school,” PLoS ONE, vol. 15, no. 4, Art no. e0231381, 2020.
https://doi.org/10.1371/journal.pone.0231381
[6] R. Ghorbani and R. Ghousi, “Comparing different resampling methods in 
predicting students’ performance using machine learning techniques,”
IEEE Access, vol. 8, pp. 67899–67911, Apr. 2020. 
https://doi.org/10.1109/ACCESS.2020.2986809
[7] I. K. Nti, A. Y. Appiah, and O. Nyarko‐Boateng, “Assessment and 
prediction of earthing resistance in domestic installation,” Engineering 
Reports, vol. 2, no. 1, Art no. e12090, Jan. 2020. 
https://doi.org/10.1002/eng2.12090
[8] I. K. Nti, M. Teimeh, A. F. Adekoya, and O. Nyarko-Boateng, 
“Forecasting electricity consumption of residential users based on 
lifestyle data using artificial neural networks,” ICTACT Journal on Soft 
Computing, vol. 10, no. 3, pp. 2107–2116, 2020. 
[9] O. Nyarko‐Boateng, A. F. Adekoya, and B. A. Weyori, “Predicting the 
actual location of faults in underground optical networks using linear 
regression,” Engineering Reports, vol. 3, no. 3, Art no. e212304, Mar. 
2021. https://doi.org/10.1002/eng2.12304
[10] O. Nyarko-Boateng, A. F. Adekoya, and B. A. Weyori, “Tracing the exact 
location of failures in underground optical networks using LSTM deep 
learning model,” Indian Journal of Science and Technology, vol. 14, 
no. 4, pp. 297–309, 2021. https://doi.org/10.17485/IJST/v14i4.2008
[11] I. K. Nti, A. F. Adekoya, and B. A. Weyori, “Efficient stock-market 
prediction using ensemble support vector machine,” Open Computer 
Science, vol. 10, no. 1, pp. 153–163, Jul. 2020. 
https://doi.org/10.1515/comp-2020-0199
[12] I. K. Nti, A. F. Adekoya, and B. A. Weyori, “Random forest based feature 
selection of macroeconomic variables for stock market prediction,”
American Journal of Applied Sciences, vol. 16, no. 7, pp. 200–212, Jul. 
2019. https://doi.org/10.3844/ajassp.2019.200.212
[13] F. Ecer, S. Ardabili, S. S. Band, and A. Mosavi, “Training multilayer 
perceptron with genetic algorithms and particle swarm optimization for 
modeling stock price index prediction,” Entropy, vol. 22, no. 11, Art no.
1239, 2020. https://doi.org/10.3390/e22111239
[14] Isha, S. Dixit, M. K. Ahirwar, D. Sakethnath, and M. Rakha, “Stock 
prediction by analyzing the past market trend,” in 2021 9th International 
Conference on Reliability, Infocom Technologies and Optimization 
(Trends and Future Directions) (ICRITO), Noida, India, Sep. 2021, pp. 1–
4. https://doi.org/10.1109/ICRITO51393.2021.9596263
[15] I. K. Nti and J. A. Quarcoo, “Self-motivation and academic performance 
in computer programming language using a hybridised machine learning 
technique,” International Journal of Artificial Intelligence and Expert 
Systems, vol. 8, no. 2, pp. 12–30, 2019.
[16] D. Aggarwal, S. Mittal, and V. Bali, “Prediction model for classifying 
students based on performance using machine learning techniques,”
International Journal of Recent Technology and Engineering, vol. 8, 
no. 2S7, pp. 496–503, Jul. 2019. 
https://doi.org/10.35940/ijrte.B1093.0782S719
[17] S. Hussain, N. A. Dahan, F. M. Ba-Alwi, and N. Ribata, “Educational data 
mining and analysis of students’ academic performance using WEKA,”
Indonesian Journal of Electrical Engineering and Computer Science,
vol. 9, no. 2, pp. 447–459, 2018. 
https://doi.org/10.11591/ijeecs.v9.i2.pp447-459
[18] H. Almarabeh, “Analysis of students’ performance by using different data 
mining classifiers,” International Journal of Modern Education and 
Computer Science, vol. 9, no. 8, pp. 9–15, Aug. 2017. 
https://doi.org/10.5815/ijmecs.2017.08.02

