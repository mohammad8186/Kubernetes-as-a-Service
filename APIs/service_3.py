from flask import Flask, jsonify
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Load Kubernetes configuration
config.load_kube_config()

@app.route('/status/all', methods=['GET'])
def get_all_applications_status():
    apps_v1 = client.AppsV1Api()
    v1 = client.CoreV1Api()

    try:
        deployments = apps_v1.list_namespaced_deployment(namespace="default")

        all_statuses = []
        for deployment in deployments.items:

            app_name = deployment.metadata.name

            if app_name == "nginx-ingress-ingress-nginx-controller":
                 continue

            replicas = deployment.spec.replicas

            # Initialize ready replicas counter
            ready_replicas = 0

            pod_list = v1.list_namespaced_pod(namespace="default", label_selector=f"app={app_name}")

            pod_statuses = []
            for pod in pod_list.items:
                phase = pod.status.phase

                # Check each container's readiness
                containers_ready = True  # Assume all containers are ready unless proven otherwise
                for container_status in pod.status.container_statuses or []:
                    if not container_status.ready:
                        containers_ready = False
                        break

                if phase == "Running" and containers_ready:
                    ready_replicas += 1

                # Check for specific conditions like CrashLoopBackOff, ImagePullBackOff, Completed
                for container_status in pod.status.container_statuses or []:
                    if container_status.state.waiting:
                        reason = container_status.state.waiting.reason
                        if reason in ["CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull", "Pending"]:
                            phase = reason
                            break
                    if container_status.state.terminated:
                        if container_status.state.terminated.reason == "Completed":
                            phase = "Completed"

                pod_status = {
                    "Name": pod.metadata.name,
                    "Phase": phase,
                    "HostIP": pod.status.host_ip,
                    "PodIP": pod.status.pod_ip,
                    "StartTime": pod.status.start_time.strftime("%Y-%m-%d %H:%M:%SZ") if pod.status.start_time else None
                }
                pod_statuses.append(pod_status)

            status = {
                "DeploymentName": app_name,
                "Replicas": replicas,
                "ReadyReplicas": ready_replicas,
                "PodStatuses": pod_statuses
            }

            all_statuses.append(status)

        return jsonify(all_statuses), 200
    except ApiException as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)