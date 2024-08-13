from flask import Flask, request, jsonify
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from flask_cors import CORS
import base64
import random
import string
import os

app = Flask(__name__)
CORS(app)
config.load_kube_config()

@app.route('/deploy_postgres', methods=['POST'])
def deploy_postgres():
    try:
        data = request.json
        app_name = data['AppName']
        resources = data['Resources']
        external = data['External']

        config_data = read_config_file('postgresql.conf')

        username, password = generate_credentials()
        create_secret(app_name, username, password)
        create_configmap(app_name, config_data)
        create_statefulset(app_name, resources)
        create_service(app_name, external)
        if external:
            create_ingress(app_name)

        return jsonify({"message": "PostgreSQL deployment initiated"}), 200

    except ApiException as e:
        return jsonify({"error": str(e)}), e.status
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def read_config_file(filepath):
    config_data = {}
    with open(filepath, 'r') as file:
        for line in file:
            if line.strip():  # Skip empty lines
                key, value = line.split('=')
                config_data[key.strip()] = value.strip()
    return {
        'postgresql.conf': f"shared_buffers = {config_data['shared_buffers']}\nmax_connections = {config_data['max_connections']}"
    }

def generate_credentials():
    username = 'postgres_user'
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    return username, password

def create_secret(app_name, username, password):
    v1 = client.CoreV1Api()
    secret_data = {
        'username': base64.b64encode(username.encode('utf-8')).decode('utf-8'),
        'password': base64.b64encode(password.encode('utf-8')).decode('utf-8')
    }
    secret = client.V1Secret(
        metadata=client.V1ObjectMeta(name=f"{app_name}-secret"),
        data=secret_data
    )
    v1.create_namespaced_secret(namespace="default", body=secret)

def create_configmap(app_name, config_data):
    v1 = client.CoreV1Api()
    configmap = client.V1ConfigMap(
        metadata=client.V1ObjectMeta(name=f"{app_name}-config"),
        data=config_data
    )
    v1.create_namespaced_config_map(namespace="default", body=configmap)

def create_statefulset(app_name, resources):
    apps_v1 = client.AppsV1Api()
    container = client.V1Container(
        name=app_name,
        image='postgres:latest',
        ports=[client.V1ContainerPort(container_port=5432)],
        env=[
            client.V1EnvVar(name='POSTGRES_USER', value_from=client.V1EnvVarSource(
                secret_key_ref=client.V1SecretKeySelector(name=f"{app_name}-secret", key='username'))),
            client.V1EnvVar(name='POSTGRES_PASSWORD', value_from=client.V1EnvVarSource(
                secret_key_ref=client.V1SecretKeySelector(name=f"{app_name}-secret", key='password')))
        ],
        volume_mounts=[client.V1VolumeMount(name=f"{app_name}-config", mount_path='/etc/postgresql/postgresql.conf', sub_path='postgresql.conf')],
        resources=client.V1ResourceRequirements(
            requests={"cpu": resources["cpu"], "memory": resources["memory"]}
        )
    )

    volume = client.V1Volume(
        name=f"{app_name}-config",
        config_map=client.V1ConfigMapVolumeSource(name=f"{app_name}-config")
    )

    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": app_name}),
        spec=client.V1PodSpec(containers=[container], volumes=[volume])
    )

    spec = client.V1StatefulSetSpec(
        service_name=app_name,
        replicas=1,
        selector={'matchLabels': {'app': app_name}},
        template=template,
        volume_claim_templates=[client.V1PersistentVolumeClaim(
            metadata=client.V1ObjectMeta(name=f"{app_name}-pvc"),
            spec=client.V1PersistentVolumeClaimSpec(
                access_modes=["ReadWriteOnce"],
                resources=client.V1ResourceRequirements(
                    requests={"storage": "1Gi"}
                )
            )
        )]
    )

    statefulset = client.V1StatefulSet(
        metadata=client.V1ObjectMeta(name=app_name),
        spec=spec
    )

    apps_v1.create_namespaced_stateful_set(namespace="default", body=statefulset)

def create_service(app_name, external):
    v1 = client.CoreV1Api()
    service = client.V1Service(
        metadata=client.V1ObjectMeta(name=app_name),
        spec=client.V1ServiceSpec(
            selector={"app": app_name},
            ports=[client.V1ServicePort(port=5432, target_port=5432)]
        )
    )
    if external:
        service.spec.type = "LoadBalancer"
    v1.create_namespaced_service(namespace="default", body=service)

def create_ingress(app_name):
    networking_v1 = client.NetworkingV1Api()
    ingress = client.V1Ingress(
        metadata=client.V1ObjectMeta(name=app_name),
        spec=client.V1IngressSpec(
            rules=[
                client.V1IngressRule(
                    host=f"{app_name}.example.com",
                    http=client.V1HTTPIngressRuleValue(
                        paths=[
                            client.V1HTTPIngressPath(
                                path="/",
                                path_type="Prefix",
                                backend=client.V1IngressBackend(
                                    service=client.V1IngressServiceBackend(
                                        name=app_name,
                                        port=client.V1ServiceBackendPort(number=5432)
                                    )
                                )
                            )
                        ]
                    )
                )
            ]
        )
    )
    networking_v1.create_namespaced_ingress(namespace="default", body=ingress)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003, debug=True)