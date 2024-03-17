import os
import pulumi
import pulumi_kubernetes as k8s
from src.cert_manager.deploy import deploy_cert_manager
from pulumi_kubernetes.apiextensions.CustomResource import CustomResource

config = pulumi.Config()
kubeconfig = os.getenv("KUBECONFIG")  or ".kube/config"
kubeconfig_context = config.get('kubecontext') or "kind-kind"
kubernetes_distribution = config.get('kubernetes') or "kind"

k8s_provider = k8s.Provider(
    "k8sProvider",
    context=kubeconfig_context,
    kubeconfig=kubeconfig,
    suppress_deprecation_warnings=True,
    suppress_helm_hook_warnings=True,
    enable_server_side_apply=True
)

cert_manager = deploy_cert_manager(
    "kargo",
    k8s_provider,
    kubernetes_distribution,
    "kargo",
    "cert-manager"
)

cert_cfg = {
    "name": "example",
    "namespace": "default",
    "secretName": "example.com",
    "issuerName": "cluster-selfsigned-issuer",
    "renewBefore": "360h0m0s",
    "duration": "2160h0m0s",
    "keyAlgorithm": "ECDSA",
    "keySize": 256,
    "dnsNames": [
        "example.com",
        "www.example.com",
        "my.example.com"
    ]
}

certificate = CustomResource(
    f"cr-certificate-{cert_cfg['namespace']}-{cert_cfg['name']}",
    api_version="cert-manager.io/v1",
    kind="Certificate",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name=cert_cfg["name"],
        namespace=cert_cfg["namespace"]
    ),
    spec={
        'secretName': cert_cfg["secretName"],
        'issuerRef': {
            'group': "cert-manager.io",
            'kind': "ClusterIssuer",
            'name': cert_cfg["issuerName"],
        },
        'commonName': cert_cfg["dnsNames"][0],
        'dnsNames': cert_cfg["dnsNames"],
        'duration': cert_cfg["duration"],
        'renewBefore': cert_cfg["renewBefore"],
        'privateKey': {
            'algorithm': cert_cfg["keyAlgorithm"],
            'size': cert_cfg["keySize"],
        },
    },
    opts=pulumi.ResourceOptions(
        provider=k8s_provider,
        depends_on=[cert_manager],
        custom_timeouts=pulumi.CustomTimeouts(
            create="5m",
            update="10m",
            delete="10m"
        )
    )
)

certificate_secret = certificate.spec.apply(lambda x: x['secretName'])
tls_secret = k8s.core.v1.Secret.get("tls_secret", certificate_secret)

ca_crt = tls_secret.data.apply(lambda d: d["ca.crt"])
tls_crt = tls_secret.data.apply(lambda d: d["tls.crt"])
tls_key = tls_secret.data.apply(lambda d: d["tls.key"])

# Export secrets for use in other stacks
pulumi.export('ca_crt', ca_crt)
pulumi.export('tls_crt', tls_crt)
pulumi.export('tls_key', tls_key)

# Pulumi Exports
pulumi.export('example_certificate', certificate_secret)
pulumi.export('cert_manager', cert_manager.name)
