# kubernetese-as-a-Service-


this application with distributed structure acts like a simple kubernetese services like creating deployments and services ans secrets which are main k8s components and objects.

the app is written in pythin(flask) and has 4 APIs(services or back-ends) and 4 UIs(front-ends) which are written with css,html,javascript .

1.the first service is responsible for create deployment and service and secret .
this is how user give input to UI of service 1:
![1](https://github.com/user-attachments/assets/f7e5f600-0c3c-49a1-aab8-41c9baecd5c4)


2.the second service is responsible for getting a status of pod:
this is how user gets result when gives deployment-name as input:
![2](https://github.com/user-attachments/assets/b3b5b996-fb3e-42df-9d8e-6fe96e9c9f05)



3.the third service is responsible for getting all deploymets status in specific namepace which is defulat.
this is how user gets result from service 3:
![3](https://github.com/user-attachments/assets/c34c94d3-7d23-4085-8ce9-b23e6c681593)



4.the fourth service is responsible for creaintg Statefulset which is Postgres database .
this is how user gets result from service 4:
![4](https://github.com/user-attachments/assets/41c87062-f59c-41d1-bbd7-1fceaf2b7686)


# if you are in mood , see the code :)
