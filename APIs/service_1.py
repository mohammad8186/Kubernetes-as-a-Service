from flask import Flask, request, jsonify
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import base64
from flask_cors import CORS




app = Flask(__name__)
CORS(app)
# Load Kubernetes configuration
config.load_kube_config()


@app.route('/deploy', methods=['POST'])
def deploy_application():

    try:
        data = request.json
        # Log the received data for debugging
        print("Received data:", data)

        app_name = data['AppName']
        replicas = data['Replicas']
        image_address = data['ImageAddress']
        image_tag = data['ImageTag']
        domain_address = data['DomainAddress']
        service_port = data['ServicePort']
        resources = data['Resources']
        envs = data['Envs']

        create_k8s_objects(app_name, replicas, image_address, image_tag, domain_address, service_port, resources, envs)

        return jsonify({"message": "Deployment initiated"}), 200

    except ApiException as e:
        if e.status == 409:
            return jsonify({"error": "Conflict: A resource with the same name already exists."}), 409
        else:
            return jsonify({"error": str(e)}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def create_k8s_objects(app_name, replicas, image_address, image_tag, domain_address, service_port, resources, envs):
    v1 = client.CoreV1Api()
    apps_v1 = client.AppsV1Api()
    networking_v1 = client.NetworkingV1Api()

    create_secret(v1, app_name, envs)
    create_deployment(apps_v1, app_name, replicas, image_address, image_tag, resources, envs, service_port)
    create_service(v1, app_name, service_port)
    create_ingress(networking_v1, app_name, domain_address, service_port)


def create_secret(v1, app_name, envs):
    secret_data = {}

    try:
        for env in envs:
            if env['IsSecret']:
                secret_data[env['Key']] = base64.b64encode(env['Value'].encode('utf-8')).decode('utf-8')

        if secret_data:
            secret = client.V1Secret(
                metadata=client.V1ObjectMeta(name=f"{app_name}-secret"),
                data=secret_data
            )
            v1.create_namespaced_secret(namespace="default", body=secret)

    except ApiException as e:
        print(f"Exception when creating secret: {e}")
        raise

    except Exception as e:
        print(f"Unexpected exception when creating secret: {e}")
        raise


def create_deployment(apps_v1, app_name, replicas, image_address, image_tag, resources, envs, service_port):
    container = client.V1Container(
        name=app_name,
        image=f"{image_address}:{image_tag}",
        ports=[client.V1ContainerPort(container_port=service_port)],
        env=[client.V1EnvVar(name=env['Key'], value=env['Value']) for env in envs if not env['IsSecret']] +
            [client.V1EnvVar(name=env['Key'], value_from=client.V1EnvVarSource(
                secret_key_ref=client.V1SecretKeySelector(name=f"{app_name}-secret", key=env['Key']))) for env in envs
             if env['IsSecret']],
        resources=client.V1ResourceRequirements(
            requests={"cpu": resources["CPU"], "memory": resources["RAM"]}
        )
    )

    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": app_name}),
        spec=client.V1PodSpec(containers=[container])
    )

    spec = client.V1DeploymentSpec(
        replicas=replicas,
        template=template,
        selector={'matchLabels': {'app': app_name}}
    )

    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name=app_name),
        spec=spec
    )

    apps_v1.create_namespaced_deployment(namespace="default", body=deployment)


def create_service(v1, app_name, service_port):
    service = client.V1Service(
        metadata=client.V1ObjectMeta(name=app_name),
        spec=client.V1ServiceSpec(
            selector={"app": app_name},
            ports=[client.V1ServicePort(port=service_port, target_port=service_port)]
        )
    )

    v1.create_namespaced_service(namespace="default", body=service)


def create_ingress(networking_v1, app_name, domain_address, service_port):
    ingress = client.V1Ingress(
        metadata=client.V1ObjectMeta(name=app_name),
        spec=client.V1IngressSpec(
            rules=[
                client.V1IngressRule(
                    host=domain_address,
                    http=client.V1HTTPIngressRuleValue(
                        paths=[
                            client.V1HTTPIngressPath(
                                path="/",
                                path_type="Prefix",
                                backend=client.V1IngressBackend(
                                    service=client.V1IngressServiceBackend(
                                        name=app_name,
                                        port=client.V1ServiceBackendPort(number=service_port)
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
    app.run(host="0.0.0.0", port=5000, debug=True)